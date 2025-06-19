
# Grad-CAM template using PyTorch
# Install with: pip install torch torchvision

import torch
from torchvision import models, transforms
from PIL import Image
import cv2
import numpy as np
import matplotlib.pyplot as plt

# Load pre-trained model
model = models.resnet50(pretrained=True)
model.eval()

# Define hook
features_blobs = []
def hook_feature(module, input, output):
    features_blobs.append(output.cpu().data.numpy())

finalconv_name = 'layer4'
model._modules.get(finalconv_name).register_forward_hook(hook_feature)

# Load image
img_path = 'example.jpg'
img = Image.open(img_path).convert('RGB')
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
input_tensor = transform(img).unsqueeze(0)

# Forward pass
logits = model(input_tensor)

# Grad-CAM
weight_softmax = model.fc.weight.data.numpy()
class_idx = np.argmax(logits.data.numpy())

bz, nc, h, w = features_blobs[0].shape
cam = weight_softmax[class_idx].dot(features_blobs[0].reshape((nc, h*w)))
cam = cam.reshape(h, w)
cam = cam - np.min(cam)
cam_img = cam / np.max(cam)
cam_img = np.uint8(255 * cam_img)
cam_img = cv2.resize(cam_img, (224, 224))
heatmap = cv2.applyColorMap(cam_img, cv2.COLORMAP_JET)

# Overlay
img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
result = heatmap * 0.4 + img_cv * 0.6
cv2.imwrite("gradcam_output.jpg", result)
