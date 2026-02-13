from PIL import Image

# notepadplusplusplus.png to notepadplusplusplus.ico
img = Image.open('notepadplusplusplus.png')
img = img.convert('RGBA')
img.save('notepadplusplusplus.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print('Icon saved as notepadplusplusplus.ico')
