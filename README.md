# <div align="center">Image Classification & Representation Learning ToolBox</div>

## 🚀 Quick Start

<summary><b>Installation Guide</b></summary>

```bash
# Create and activate environment
conda create -n vision python=3.10 && conda activate vision

# Install PyTorch (CUDA or CPU version)
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y
# or
conda install pytorch torchvision torchaudio cpuonly -c pytorch -y

# Install dependencies
pip install -r requirements.txt

# For CBIR functionality
conda install faiss-gpu=1.8.0 -c pytorch

# Optional: Install Arial font for faster inference
mkdir -p ~/.config/DuKe && cp misc/Arial.ttf ~/.config/DuKe
```
