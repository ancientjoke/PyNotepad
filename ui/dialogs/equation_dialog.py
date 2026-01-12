"""
Equation Dialog

Dialog for inserting LaTeX equations into documents.
Provides a preview of the rendered equation.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QFrame,
    QDialogButtonBox,
    QComboBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QImage, QPixmap


class EquationDialog(QDialog):
    """
    Dialog for entering and previewing LaTeX equations.
    """
    
    # Common equation templates
    TEMPLATES = {
        "Fraction": r"\frac{a}{b}",
        "Square Root": r"\sqrt{x}",
        "Nth Root": r"\sqrt[n]{x}",
        "Superscript": r"x^{2}",
        "Subscript": r"x_{i}",
        "Sum": r"\sum_{i=1}^{n} x_i",
        "Product": r"\prod_{i=1}^{n} x_i",
        "Integral": r"\int_{a}^{b} f(x) dx",
        "Limit": r"\lim_{x \to \infty} f(x)",
        "Matrix 2x2": r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
        "Matrix 3x3": r"\begin{pmatrix} a & b & c \\ d & e & f \\ g & h & i \end{pmatrix}",
        "Greek Alpha": r"\alpha",
        "Greek Beta": r"\beta",
        "Greek Pi": r"\pi",
        "Greek Sigma": r"\sigma",
        "Greek Theta": r"\theta",
        "Infinity": r"\infty",
        "Plus/Minus": r"\pm",
        "Not Equal": r"\neq",
        "Less/Equal": r"\leq",
        "Greater/Equal": r"\geq",
        "Approximately": r"\approx",
        "Derivative": r"\frac{d}{dx} f(x)",
        "Partial Derivative": r"\frac{\partial f}{\partial x}",
        "Vector": r"\vec{v}",
        "Hat": r"\hat{x}",
        "Bar": r"\bar{x}",
        "Binomial": r"\binom{n}{k}",
        "Quadratic Formula": r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        "Pythagorean Theorem": r"a^2 + b^2 = c^2",
        "Euler's Identity": r"e^{i\pi} + 1 = 0",
    }
    
    def __init__(self, parent: Optional[QDialog] = None):
        super().__init__(parent)
        
        self.setWindowTitle("Insert Equation")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Set up dialog UI."""
        layout = QVBoxLayout(self)
        
        # Templates section
        templates_group = QGroupBox("Templates")
        templates_layout = QHBoxLayout(templates_group)
        
        self._template_combo = QComboBox()
        self._template_combo.addItem("-- Select Template --")
        for name in self.TEMPLATES.keys():
            self._template_combo.addItem(name)
        templates_layout.addWidget(self._template_combo)
        
        self._insert_template_btn = QPushButton("Insert")
        templates_layout.addWidget(self._insert_template_btn)
        templates_layout.addStretch()
        
        layout.addWidget(templates_group)
        
        # LaTeX input section
        input_group = QGroupBox("LaTeX Code")
        input_layout = QVBoxLayout(input_group)
        
        self._latex_edit = QTextEdit()
        self._latex_edit.setFont(QFont("Consolas", 11))
        self._latex_edit.setPlaceholderText("Enter LaTeX equation...\nExample: \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}")
        self._latex_edit.setMinimumHeight(100)
        input_layout.addWidget(self._latex_edit)
        
        layout.addWidget(input_group)
        
        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(100)
        self._preview_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 20px;
            }
        """)
        self._preview_label.setText("Preview will appear here")
        preview_layout.addWidget(self._preview_label)
        
        self._preview_btn = QPushButton("Update Preview")
        preview_layout.addWidget(self._preview_btn)
        
        layout.addWidget(preview_group)
        
        # Help text
        help_label = QLabel(
            "<small>Tips: Use \\frac{}{} for fractions, ^{} for superscript, "
            "_{} for subscript, \\sqrt{} for square root</small>"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _connect_signals(self) -> None:
        """Connect signals."""
        self._insert_template_btn.clicked.connect(self._insert_template)
        self._preview_btn.clicked.connect(self._update_preview)
        self._latex_edit.textChanged.connect(self._on_text_changed)
    
    def _insert_template(self) -> None:
        """Insert selected template into editor."""
        name = self._template_combo.currentText()
        if name in self.TEMPLATES:
            latex = self.TEMPLATES[name]
            cursor = self._latex_edit.textCursor()
            cursor.insertText(latex)
            self._latex_edit.setFocus()
    
    def _on_text_changed(self) -> None:
        """Handle text change - auto preview with delay."""
        pass  # Could add delayed auto-preview here
    
    def _update_preview(self) -> None:
        """Render and show preview."""
        latex = self._latex_edit.toPlainText().strip()
        if not latex:
            self._preview_label.setText("Enter LaTeX code to preview")
            return
        
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from io import BytesIO
            
            fig, ax = plt.subplots(figsize=(0.01, 0.01))
            ax.axis('off')
            
            # Render the LaTeX
            text = ax.text(0.5, 0.5, f"${latex}$", 
                          transform=ax.transAxes,
                          fontsize=16,
                          ha='center', va='center')
            
            # Get bounding box
            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer())
            
            # Resize figure
            fig.set_size_inches(bbox.width / fig.dpi + 0.4, bbox.height / fig.dpi + 0.4)
            
            # Save to buffer
            buffer = BytesIO()
            fig.savefig(buffer, format='png', dpi=150, 
                       bbox_inches='tight', pad_inches=0.2,
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            buffer.seek(0)
            image = QImage()
            image.loadFromData(buffer.getvalue())
            
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                # Scale if too large
                if pixmap.width() > 500:
                    pixmap = pixmap.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation)
                self._preview_label.setPixmap(pixmap)
            else:
                self._preview_label.setText("Failed to render preview")
                
        except ImportError:
            self._preview_label.setText(
                "<b>Preview unavailable</b><br>"
                "Install matplotlib for LaTeX preview:<br>"
                "<code>pip install matplotlib</code>"
            )
        except Exception as e:
            self._preview_label.setText(f"<b>Error:</b> {str(e)}")
    
    def get_latex(self) -> str:
        """Get the entered LaTeX code."""
        return self._latex_edit.toPlainText().strip()
    
    def set_latex(self, latex: str) -> None:
        """Set the LaTeX code."""
        self._latex_edit.setPlainText(latex)
