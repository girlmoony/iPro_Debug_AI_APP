import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
from torch.quantization import get_default_qat_qconfig, prepare_qat, convert

# === 1. モデルを定義（QAT用） ===
num_classes = 288  # 例：284+4
model = efficientnet_b0(pretrained=True)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)

# === 2. QAT設定を再構成 ===
model.qconfig = get_default_qat_qconfig('fbgemm')
model_prepared = prepare_qat(model)

# === 3. QATで保存したstate_dictを読み込む ===
state_dict = torch.load("qat_model.pth", map_location='cpu')
model_prepared.load_state_dict(state_dict)

# === 4. convert()で量子化を確定（FakeQuant層を削除） ===
model_quantized = convert(model_prepared.eval())

# === 5. ダミー入力でONNX変換 ===
dummy_input = torch.randn(1, 3, 224, 224)  # 入力サイズに合わせて調整
torch.onnx.export(
    model_quantized,
    dummy_input,
    "model_qat.onnx",
    input_names=["input"],
    output_names=["output"],
    opset_version=13,
    do_constant_folding=True
)

print("✅ 量子化済みモデルを ONNX に変換しました：model_qat.onnx")
