from engine import increment_path
from dataset.transforms import create_AugTransforms
from utils.plots import colorstr
from dataset.basedataset import PredictImageDatasets
from torch.utils.data import DataLoader
import os
import argparse
from pathlib import Path
import torch
import json
import time
from engine import CenterProcessor, yaml_load, Visualizer
from utils.logger import SmartLogger
from models.faceX.face_model import FaceModelLoader
from engine.cbir.evaluation import valuate as valuate_cbir
from tqdm import tqdm

LOCAL_RANK = int(os.getenv('LOCAL_RANK', -1))
ROOT = Path(os.path.dirname(__file__))

def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfgs', default = 'run/exp8/pet.yaml', help='Configs for models, data, hyps')
    parser.add_argument('--weight', default = 'run/exp/best.pt', help='Configs for models, data, hyps')

    # classification
    parser.add_argument('--data', default = ROOT / 'data/val/a', help='Target data directory')
    parser.add_argument('--target_class', default = None, help='Which class do you want to check')
    parser.add_argument('--no_annotation', action='store_true', help = 'Do not write result in top-left')
    parser.add_argument('--cam', action='store_true', help = 'Advanced AI explainability')
    parser.add_argument('--ema', action='store_true', help = 'Exponential Moving Average for model weight')
    parser.add_argument('--class_json', default = 'run/exp/class_indices.json', type=str)
    parser.add_argument('--badcase', action='store_true', help='Automatically organize badcases')

    # CBIR
    parser.add_argument('--max_rank', default=10, type=int, help='Visualize top k retrieval results')

    # Unless specific needs, it is generally not modified below.
    parser.add_argument('--show_path', default = ROOT / 'visualization')
    parser.add_argument('--name', default = 'exp')
    parser.add_argument('--local_rank', type=int, default=-1, help='Automatic DDP Multi-GPU argument, do not modify')

    return parser.parse_args()

if __name__ == '__main__':

    opt = parse_opt()
    visual_dir = increment_path(Path(opt.show_path) / opt.name)

    cfgs = yaml_load(opt.cfgs)
    task: str = cfgs['model']['task']
    if task == 'classification':
        cpu = CenterProcessor(cfgs, LOCAL_RANK, train=False, opt=opt)

        # checkpoint loading
        model = cpu.model_processor.model
        if opt.ema:
            weights = torch.load(opt.weight, map_location=cpu.device)['ema'].float().state_dict()
        else:
            weights = torch.load(opt.weight, map_location=cpu.device)['model']
        model.load_state_dict(weights)

        with open(opt.class_json, 'r', encoding='utf-8') as f:
            class_dict = json.load(f)
            class_dict = dict((eval(k), v) for k,v in class_dict.items())

        dataset = PredictImageDatasets(opt.data,
                                    transforms=create_AugTransforms(cpu.data_cfg['val']['augment']))
        dataloader = DataLoader(dataset, shuffle=False, pin_memory=True, num_workers=cpu.data_cfg['nw'], batch_size=1,
                                collate_fn=PredictImageDatasets.collate_fn)

        t0 = time.time()
        Visualizer.predict_images(model,
                    dataloader,
                    opt.data,
                    cpu.device,
                    visual_dir,
                    class_dict,
                    cpu.logger,
                    'ce' if cpu.thresh == 0 else 'bce',
                    opt.badcase,
                    opt.cam,
                    opt.no_annotation,
                    opt.target_class
                    )

        cpu.logger.console(f'\nPredicting complete ({(time.time() - t0) / 60:.3f} minutes)'
                    f"\nResults saved to {colorstr('bold', visual_dir)}")
    elif task in ('face', 'cbir'):
        # logger
        logger = SmartLogger(filename=None)

        # checkpoint loading
        logger.console(f'loading model, ema is {opt.ema}')
        model_loader = FaceModelLoader(model_cfg=cfgs['model'])
        model = model_loader.load_weight(model_path=opt.weight, ema=opt.ema)

        cfgs['data']['val']['metrics']['cutoffs'] = [opt.max_rank]
        retrieval_results, scores, ground_truths, queries = valuate_cbir(model, 
                                                                         cfgs['data'], 
                                                                         torch.device('cuda', LOCAL_RANK if LOCAL_RANK > 0 else 0), 
                                                                         logger, 
                                                                         vis=True)

        for idx, q in tqdm(enumerate(queries), total=len(queries), desc='Visualizing', position=0):
            Visualizer.visualize_results(q, 
                                         retrieval_results[idx], 
                                         scores[idx], 
                                         ground_truths[idx],
                                         visual_dir,
                                         opt.max_rank
                                         )

    else:
        raise ValueError(f'Unknown task {task}')
