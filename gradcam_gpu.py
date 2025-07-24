import torch
import torch.nn.functional as F
import cv2
import numpy as np
from torchvision import transforms

class GradCAM:
    def __init__(self, model, target_layer):
        self.model = model.eval()
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        self.hook()

    def hook(self):
        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_in, grad_out):
            self.gradients = grad_out[0].detach()

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_backward_hook(backward_hook)

    def __call__(self, input_tensor, class_index=None):
        output = self.model(input_tensor)
        if class_index is None:
            class_index = output.argmax(dim=1).item()

        self.model.zero_grad()
        loss = output[0, class_index]
        loss.backward()

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)

        cam = F.interpolate(cam, size=input_tensor.shape[2:], mode='bilinear', align_corners=False)
        cam = cam.squeeze().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)  # normalize to [0,1]

        return cam

import matplotlib.pyplot as plt

def show_cam_on_image(img_tensor, cam):
    img = img_tensor.squeeze().permute(1, 2, 0).cpu().numpy()
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)

    heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    heatmap = np.float32(heatmap) / 255
    overlay = heatmap + img
    overlay = overlay / np.max(overlay)

    plt.imshow(overlay)
    plt.axis('off')
    plt.title("Grad-CAM Overlay")
    plt.show()
from torchvision import models
import torchvision.transforms as T
from PIL import Image

# モデルと対象層（例: features.8）指定
model = models.efficientnet_b0(pretrained=True)
target_layer = model.features[8]

gradcam = GradCAM(model, target_layer)

# 画像読み込みと変換
img = Image.open("example_sushi.jpg").convert("RGB")
transform = T.Compose([
    T.Resize((224, 224)),
    T.ToTensor(),
])
input_tensor = transform(img).unsqueeze(0)

# Grad-CAM適用
cam = gradcam(input_tensor)
show_cam_on_image(input_tensor[0], cam)
