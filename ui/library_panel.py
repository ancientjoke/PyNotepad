"""
Library Panel

Sidebar panel for managing document library, collections, and tags.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
import shutil

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QLineEdit,
    QPushButton,
    QMenu,
    QLabel,
    QSplitter,
    QToolButton,
    QFrame,
    QSizePolicy,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction


class CreateCollectionDialog(QDialog):
    """Dialog for creating a new collection."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Create Collection")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter collection name...")
        form_layout.addRow("Name:", self._name_edit)
        
        self._create_folder_check = QCheckBox("Create folder in library")
        self._create_folder_check.setChecked(True)
        form_layout.addRow("", self._create_folder_check)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._name_edit.setFocus()
    
    def get_data(self) -> dict:
        return {
            "name": self._name_edit.text().strip(),
            "create_folder": self._create_folder_check.isChecked(),
        }


class AddToCollectionDialog(QDialog):
    """Dialog for adding a document to a collection."""
    
    def __init__(self, collections: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add to Collection")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select collection:"))
        
        self._collection_combo = QComboBox()
        self._collection_combo.addItems(collections)
        layout.addWidget(self._collection_combo)
        
        self._copy_file_check = QCheckBox("Copy file to collection folder")
        self._copy_file_check.setChecked(True)
        layout.addWidget(self._copy_file_check)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_data(self) -> dict:
        return {
            "collection": self._collection_combo.currentText(),
            "copy_file": self._copy_file_check.isChecked(),
        }


class LibraryPanel(QWidget):
    """
    Library panel for document management.
    
    Signals:
        document_selected: Emitted when a document is selected (file_path)
        collection_selected: Emitted when a collection is selected (collection_id)
        tag_selected: Emitted when a tag is selected (tag_name)
    """
    
    document_selected = pyqtSignal(str)
    collection_selected = pyqtSignal(str)
    tag_selected = pyqtSignal(str)
    
    def __init__(self, services: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._services = services
        self._collections: Dict[str, dict] = {}  # name -> {path}
        self._library_path: Optional[Path] = None
        
        # Get library path from services - try different attribute names
        if "import_service" in services:
            import_svc = services["import_service"]
            self._library_path = getattr(import_svc, "_default_library_path", None)
            if self._library_path is None:
                self._library_path = getattr(import_svc, "_library_path", None)
        
        # Fallback: create library path in user data folder
        if self._library_path is None:
            from pathlib import Path
            app_data = Path.home() / ".notepadppp"
            self._library_path = app_data / "library"
            self._library_path.mkdir(parents=True, exist_ok=True)
        
        self._setup_ui()
        self._connect_signals()
        self._load_data()
    
    def _setup_ui(self) -> None:
        """Set up the library panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(8, 8, 8, 8)
        
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search library...")
        self._search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_edit)
        
        layout.addLayout(search_layout)
        
        # Splitter for tree and list
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # Collections/Tags tree
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)
        
        tree_header = QFrame()
        tree_header.setFrameShape(QFrame.Shape.StyledPanel)
        tree_header_layout = QHBoxLayout(tree_header)
        tree_header_layout.setContentsMargins(8, 4, 8, 4)
        
        tree_label = QLabel("Library")
        tree_label.setStyleSheet("font-weight: bold;")
        tree_header_layout.addWidget(tree_label)
        
        tree_header_layout.addStretch()
        
        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Add collection")
        add_btn.clicked.connect(self._on_add_collection)
        tree_header_layout.addWidget(add_btn)
        
        tree_layout.addWidget(tree_header)
        
        self._tree_widget = QTreeWidget()
        self._tree_widget.setHeaderHidden(True)
        self._tree_widget.setIndentation(16)
        self._tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree_layout.addWidget(self._tree_widget)
        
        splitter.addWidget(tree_widget)
        
        # Recent documents list
        recent_widget = QWidget()
        recent_layout = QVBoxLayout(recent_widget)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(0)
        
        recent_header = QFrame()
        recent_header.setFrameShape(QFrame.Shape.StyledPanel)
        recent_header_layout = QHBoxLayout(recent_header)
        recent_header_layout.setContentsMargins(8, 4, 8, 4)
        
        recent_label = QLabel("Recent Documents")
        recent_label.setStyleSheet("font-weight: bold;")
        recent_header_layout.addWidget(recent_label)
        
        recent_layout.addWidget(recent_header)
        
        self._recent_list = QListWidget()
        self._recent_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        recent_layout.addWidget(self._recent_list)
        
        splitter.addWidget(recent_widget)
        
        # Set splitter sizes
        splitter.setSizes([200, 200])
    
    def _connect_signals(self) -> None:
        """Connect signals."""
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        self._tree_widget.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        self._tree_widget.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_item_double_clicked)
        self._recent_list.customContextMenuRequested.connect(self._on_recent_context_menu)
    
    def _load_data(self) -> None:
        """Load library data."""
        self._load_collections()
        self._load_recent_documents()
    
    def _load_collections(self) -> None:
        """Load collections and tags into tree."""
        self._tree_widget.clear()
        self._collections.clear()
        
        # All Documents
        all_docs = QTreeWidgetItem(["All Documents"])
        all_docs.setData(0, Qt.ItemDataRole.UserRole, {"type": "all"})
        self._tree_widget.addTopLevelItem(all_docs)
        
        # Favorites
        favorites = QTreeWidgetItem(["Favorites"])
        favorites.setData(0, Qt.ItemDataRole.UserRole, {"type": "favorites"})
        self._tree_widget.addTopLevelItem(favorites)
        
        # Collections
        collections_root = QTreeWidgetItem(["Collections"])
        collections_root.setData(0, Qt.ItemDataRole.UserRole, {"type": "collections_root"})
        self._tree_widget.addTopLevelItem(collections_root)
        
        # Load collections from library folder
        if self._library_path and self._library_path.exists():
            for folder in sorted(self._library_path.iterdir()):
                if folder.is_dir() and not folder.name.startswith('.'):
                    item = QTreeWidgetItem([folder.name])
                    item.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "collection",
                        "name": folder.name,
                        "path": str(folder),
                    })
                    self._collections[folder.name] = {"path": str(folder)}
                    collections_root.addChild(item)
                    
                    # Add PDF files in collection
                    for pdf_file in sorted(folder.glob("*.pdf")):
                        file_item = QTreeWidgetItem([pdf_file.name])
                        file_item.setData(0, Qt.ItemDataRole.UserRole, {
                            "type": "document",
                            "path": str(pdf_file),
                        })
                        item.addChild(file_item)
        
        collections_root.setExpanded(True)
        
        # Tags
        tags_root = QTreeWidgetItem(["Tags"])
        tags_root.setData(0, Qt.ItemDataRole.UserRole, {"type": "tags_root"})
        self._tree_widget.addTopLevelItem(tags_root)
        
        tags_root.setExpanded(True)
    
    def _load_recent_documents(self) -> None:
        """Load recent documents."""
        self._recent_list.clear()
        
        if "document" in self._services.get("repositories", {}):
            repo = self._services["repositories"]["document"]
            result = repo.get_recent(limit=20)
            if result.is_success:
                for doc in result.value:
                    item = QListWidgetItem(doc.title or doc.file_name)
                    item.setData(Qt.ItemDataRole.UserRole, doc.file_path)
                    item.setToolTip(doc.file_path)
                    self._recent_list.addItem(item)
    
    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        # TODO: Implement search filtering
        pass
    
    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item click."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        item_type = data.get("type")
        
        if item_type == "collection":
            self.collection_selected.emit(data.get("name", ""))
        elif item_type == "tag":
            self.tag_selected.emit(data.get("name", ""))
        elif item_type == "document":
            # Double-click to open is handled separately
            pass
    
    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item double-click."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        item_type = data.get("type")
        if item_type == "document":
            file_path = data.get("path")
            if file_path:
                self.document_selected.emit(file_path)
    
    def _on_tree_context_menu(self, pos) -> None:
        """Show context menu for tree item."""
        item = self._tree_widget.itemAt(pos)
        
        menu = QMenu(self)
        
        if not item:
            # Context menu for empty space
            add_action = menu.addAction("New Collection")
            if add_action:
                add_action.triggered.connect(self._on_add_collection)
            menu.exec(self._tree_widget.mapToGlobal(pos))
            return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        item_type = data.get("type")
        
        if item_type == "collection":
            open_folder_action = menu.addAction("Open Folder")
            if open_folder_action:
                open_folder_action.triggered.connect(lambda: self._open_collection_folder(item))
            
            menu.addSeparator()
            
            add_pdf_action = menu.addAction("Add PDF to Collection")
            if add_pdf_action:
                add_pdf_action.triggered.connect(lambda: self._add_pdf_to_collection(item))
            
            menu.addSeparator()
            
            rename_action = menu.addAction("Rename")
            if rename_action:
                rename_action.triggered.connect(lambda: self._rename_collection(item))
            
            delete_action = menu.addAction("Delete")
            if delete_action:
                delete_action.triggered.connect(lambda: self._delete_collection(item))
        
        elif item_type == "collections_root":
            add_action = menu.addAction("New Collection")
            if add_action:
                add_action.triggered.connect(self._on_add_collection)
        
        elif item_type == "document":
            open_action = menu.addAction("Open")
            if open_action:
                open_action.triggered.connect(lambda: self._open_document_from_tree(item))
            
            menu.addSeparator()
            
            show_in_folder_action = menu.addAction("Show in Folder")
            if show_in_folder_action:
                show_in_folder_action.triggered.connect(lambda: self._show_document_in_folder(item))
            
            menu.addSeparator()
            
            remove_action = menu.addAction("Remove from Collection")
            if remove_action:
                remove_action.triggered.connect(lambda: self._remove_document_from_collection(item))
        
        elif item_type == "tag":
            rename_action = menu.addAction("Rename")
            if rename_action:
                rename_action.triggered.connect(lambda: self._rename_tag(item))
            
            delete_action = menu.addAction("Delete")
            if delete_action:
                delete_action.triggered.connect(lambda: self._delete_tag(item))
        
        elif item_type == "tags_root":
            add_action = menu.addAction("New Tag")
            if add_action:
                add_action.triggered.connect(self._on_add_tag)
        
        if menu.actions():
            menu.exec(self._tree_widget.mapToGlobal(pos))
    
    def _on_recent_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle recent document double-click."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.document_selected.emit(file_path)
    
    def _on_recent_context_menu(self, pos) -> None:
        """Show context menu for recent document."""
        item = self._recent_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self)
        
        open_action = menu.addAction("Open")
        if open_action:
            open_action.triggered.connect(lambda: self._open_recent_document(item))
        
        menu.addSeparator()
        
        add_to_collection_action = menu.addAction("Add to Collection")
        if add_to_collection_action:
            add_to_collection_action.triggered.connect(lambda: self._add_recent_to_collection(item))
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Remove from Recent")
        if remove_action:
            remove_action.triggered.connect(lambda: self._remove_from_recent(item))
        
        menu.exec(self._recent_list.mapToGlobal(pos))
    
    def _on_add_collection(self) -> None:
        """Add a new collection."""
        dialog = CreateCollectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            name = data["name"]
            
            if not name:
                QMessageBox.warning(self, "Error", "Collection name cannot be empty.")
                return
            
            if name in self._collections:
                QMessageBox.warning(self, "Error", f"Collection '{name}' already exists.")
                return
            
            # Create collection folder (always create folder for collections)
            if self._library_path:
                collection_path = self._library_path / name
                try:
                    collection_path.mkdir(parents=True, exist_ok=True)
                    self._collections[name] = {"path": str(collection_path)}
                    self._load_collections()
                    QMessageBox.information(self, "Success", f"Collection '{name}' created at:\n{collection_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create collection folder:\n{e}")
            else:
                QMessageBox.warning(self, "Error", "Library path not configured. Cannot create collection.")
    
    def _rename_collection(self, item: QTreeWidgetItem) -> None:
        """Rename a collection."""
        from PyQt6.QtWidgets import QInputDialog
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        current_name = item.text(0)
        old_path = data.get("path", "") if data else ""
        
        name, ok = QInputDialog.getText(
            self,
            "Rename Collection",
            "New name:",
            text=current_name,
        )
        
        if ok and name and name != current_name:
            if name in self._collections:
                QMessageBox.warning(self, "Error", f"Collection '{name}' already exists.")
                return
            
            # Rename the folder
            if old_path and self._library_path:
                old_folder = Path(old_path)
                new_folder = self._library_path / name
                try:
                    old_folder.rename(new_folder)
                    self._load_collections()
                    QMessageBox.information(self, "Success", f"Collection renamed to '{name}'.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to rename collection:\\n{e}")
    
    def _delete_collection(self, item: QTreeWidgetItem) -> None:
        """Delete a collection."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        name = data.get("name", "") if data else ""
        path = data.get("path", "") if data else ""
        
        reply = QMessageBox.question(
            self,
            "Delete Collection",
            f"Delete collection '{name}'?\n\nThis will also delete all files in the collection folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if path:
                try:
                    shutil.rmtree(path)
                    self._load_collections()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete:\\n{e}")
    
    def _open_collection_folder(self, item: QTreeWidgetItem) -> None:
        """Open collection folder in file explorer."""
        import subprocess
        import sys
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        path = data.get("path", "") if data else ""
        
        if path:
            if sys.platform == "win32":
                subprocess.run(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
    
    def _add_pdf_to_collection(self, item: QTreeWidgetItem) -> None:
        """Add a PDF file to a collection."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        collection_path = data.get("path", "") if data else ""
        
        if not collection_path:
            return
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add PDF to Collection",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        
        for file_path in file_paths:
            source = Path(file_path)
            dest = Path(collection_path) / source.name
            
            try:
                shutil.copy2(source, dest)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add {source.name}:\\n{e}")
        
        if file_paths:
            self._load_collections()
    
    def _open_document_from_tree(self, item: QTreeWidgetItem) -> None:
        """Open a document from tree."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        path = data.get("path", "") if data else ""
        if path:
            self.document_selected.emit(path)
    
    def _show_document_in_folder(self, item: QTreeWidgetItem) -> None:
        """Show document in file explorer."""
        import subprocess
        import sys
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        path = data.get("path", "") if data else ""
        
        if path:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", str(Path(path).parent)])
    
    def _remove_document_from_collection(self, item: QTreeWidgetItem) -> None:
        """Remove a document from collection (delete file)."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        path = data.get("path", "") if data else ""
        
        if not path:
            return
        
        reply = QMessageBox.question(
            self,
            "Remove Document",
            f"Remove '{Path(path).name}' from collection?\\n\\nThis will delete the file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                Path(path).unlink()
                self._load_collections()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove:\\n{e}")
    
    def _on_add_tag(self) -> None:
        """Add a new tag."""
        name, ok = QInputDialog.getText(
            self,
            "New Tag",
            "Tag name:",
        )
        
        if ok and name:
            tags_root = None
            for i in range(self._tree_widget.topLevelItemCount()):
                top_item = self._tree_widget.topLevelItem(i)
                if top_item:
                    data = top_item.data(0, Qt.ItemDataRole.UserRole)
                    if data and data.get("type") == "tags_root":
                        tags_root = top_item
                        break
            
            if tags_root:
                tag_item = QTreeWidgetItem([name])
                tag_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "tag",
                    "name": name,
                })
                tags_root.addChild(tag_item)
    
    def _rename_tag(self, item: QTreeWidgetItem) -> None:
        """Rename a tag."""
        from PyQt6.QtWidgets import QInputDialog
        
        current_name = item.text(0)
        
        name, ok = QInputDialog.getText(
            self,
            "Rename Tag",
            "New name:",
            text=current_name,
        )
        
        if ok and name:
            # TODO: Update tag via repository
            item.setText(0, name)
    
    def _delete_tag(self, item: QTreeWidgetItem) -> None:
        """Delete a tag."""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Delete Tag",
            f"Delete tag '{item.text(0)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # TODO: Delete tag via repository
            parent = item.parent()
            if parent:
                parent.removeChild(item)
    
    def _open_recent_document(self, item: QListWidgetItem) -> None:
        """Open a recent document."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.document_selected.emit(file_path)
    
    def _remove_from_recent(self, item: QListWidgetItem) -> None:
        """Remove document from recent list."""
        row = self._recent_list.row(item)
        self._recent_list.takeItem(row)
    
    def _add_recent_to_collection(self, item: QListWidgetItem) -> None:
        """Add a recent document to a collection."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        collection_names = list(self._collections.keys())
        if not collection_names:
            QMessageBox.information(
                self,
                "No Collections",
                "Please create a collection first.",
            )
            return
        
        dialog = AddToCollectionDialog(collection_names, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            collection_name = data["collection"]
            
            if collection_name in self._collections:
                collection_path = self._collections[collection_name]["path"]
                source = Path(file_path)
                dest = Path(collection_path) / source.name
                
                try:
                    if data["copy_file"]:
                        shutil.copy2(source, dest)
                    self._load_collections()
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Added '{source.name}' to '{collection_name}'.",
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add:\\n{e}")
    
    def get_collections(self) -> List[str]:
        """Get list of collection names."""
        return list(self._collections.keys())
    
    def get_collection_path(self, name: str) -> Optional[str]:
        """Get the path of a collection by name."""
        if name in self._collections:
            return self._collections[name].get("path")
        return None
    
    def refresh(self) -> None:
        """Refresh the library panel."""
        self._load_data()
