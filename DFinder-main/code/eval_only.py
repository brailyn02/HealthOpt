"""Run evaluation only on the saved checkpoint."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import world
import utils
import dataloader
import model
import Procedure
import torch
from pprint import pprint

# Setup
world.tensorboard = False
world.config['test_u_batch_size'] = 332
dataset = dataloader.Loader(path=f"../data/{world.dataset}")

# Build model
Recmodel = model.LightGCN(world.config, dataset)
Recmodel = Recmodel.to(world.device)

# Load checkpoint
weight_file = utils.getFileName()
print(f"Loading: {weight_file}")
Recmodel.load_state_dict(torch.load(weight_file, map_location=world.device))
Recmodel.eval()

# Run eval
results = Procedure.Test(dataset, Recmodel, epoch=500, w=None, multicore=world.config['multicore'])
print("\n=== Final Evaluation Results ===")
pprint(results)
