import torch
from torchvision import transforms
from torchvision.transforms import ToPILImage, ToTensor, ColorJitter, RandomHorizontalFlip, RandomVerticalFlip, RandomRotation, GaussianBlur, Normalize
from PIL import Image
import matplotlib.pyplot as plt

# サンプル画像を読み込み（好きなパスに変更してください）
image_path = 'sample.jpg'
img = Image.open(image_path).convert('RGB')

# 変換定義
transform = transforms.Compose([
    ToPILImage(),
    ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3),
    RandomHorizontalFlip(0.1),
    RandomVerticalFlip(0.1),
    RandomRotation(180),
    GaussianBlur(kernel_size=11),
    ToTensor(),
    Normalize([0.485, 0.456, 0.406],
              [0.229, 0.224, 0.225])
])

# PIL→Tensor→PILのためTensor化
img_tensor = ToTensor()(img)
transformed_img_tensor = transform(img_tensor)
# Tensor→PIL変換（正規化戻しも含めて表示用）
unnormalize = transforms.Normalize(
    mean=[-0.485/0.229, -0.456/0.224, -0.406/0.225],
    std=[1/0.229, 1/0.224, 1/0.225]
)
display_tensor = unnormalize(transformed_img_tensor).clamp(0, 1)
display_img = ToPILImage()(display_tensor)

# 表示
plt.imshow(display_img)
plt.axis('off')
plt.title('All Transforms Applied')
plt.show()

#change parameter to check the image

import matplotlib.pyplot as plt
from PIL import Image
from torchvision.transforms import ToTensor, ToPILImage, GaussianBlur, ColorJitter

# 画像パス（任意の画像に変更してください）
image_path = 'sample.jpg'

# 画像読み込み
img = Image.open(image_path).convert('RGB')

# 各変換
blur_transform = GaussianBlur(kernel_size=5)
colorjitter_transform = ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3)

# 変換適用
blur_img = blur_transform(img)
colorjitter_img = colorjitter_transform(img)

# 表示
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# 元画像
axes[0].imshow(img)
axes[0].set_title('Original Image')
axes[0].axis('off')

# GaussianBlur画像
axes[1].imshow(blur_img)
axes[1].set_title('GaussianBlur (kernel_size=5)')
axes[1].axis('off')

# ColorJitter画像
axes[2].imshow(colorjitter_img)
axes[2].set_title('ColorJitter (brightness=0.3, contrast=0.3, saturation=0.3)')
axes[2].axis('off')

plt.show()

#cv2を使う

import cv2
from PIL import Image
import matplotlib.pyplot as plt
from torchvision.transforms import ToPILImage, GaussianBlur, ColorJitter

# 画像パス（好きな画像パスに変更してください）
image_path = 'sample.jpg'

# cv2で画像読み込み（BGR → RGB変換）
img_cv2 = cv2.imread(image_path)
img_cv2 = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB)

# 必要ならcv2でresize（例：224×224）
img_cv2 = cv2.resize(img_cv2, (224, 224))

# numpy配列 → PIL画像に変換
img = Image.fromarray(img_cv2)

# 各変換
blur_transform = GaussianBlur(kernel_size=5)
colorjitter_transform = ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3)

# 変換適用
blur_img = blur_transform(img)
colorjitter_img = colorjitter_transform(img)

# 表示
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

axes[0].imshow(img)
axes[0].set_title('Original Image')
axes[0].axis('off')

axes[1].imshow(blur_img)
axes[1].set_title('GaussianBlur (kernel_size=5)')
axes[1].axis('off')

axes[2].imshow(colorjitter_img)
axes[2].set_title('ColorJitter (brightness=0.3, contrast=0.3, saturation=0.3)')
axes[2].axis('off')

plt.show()

