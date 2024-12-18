import os
import time
import copy
import torch
import torch.optim as optim
import pprint as pp
# import utils.hypergraph_utils as hgut
import utils.new_utils as hgut
from models import HGNN
from config import get_config
# from datasets import load_feature_construct_H
from datasets.new_data_helper import load_feature_construct_H_and_R

# import libraries for seeding
import numpy as np
import random

os.environ['CUDA_VISIBLE_DEVICES'] = '0'
cfg = get_config('config/config.yaml')

# initialize data
# data_dir = cfg['modelnet40_ft'] if cfg['on_dataset'] == 'ModelNet40' \
#     else cfg['ntu2012_ft']
# fts, lbls, idx_train, idx_test, H = \
#     load_feature_construct_H(data_dir,
#                              m_prob=cfg['m_prob'],
#                              K_neigs=cfg['K_neigs'],
#                              is_probH=cfg['is_probH'],
#                              use_mvcnn_feature=cfg['use_mvcnn_feature'],
#                              use_gvcnn_feature=cfg['use_gvcnn_feature'],
#                              use_mvcnn_feature_for_structure=cfg['use_mvcnn_feature_for_structure'],
#                              use_gvcnn_feature_for_structure=cfg['use_gvcnn_feature_for_structure'])
data_dir = cfg['data_root']
H, R, E_weights, X, Y, idx_train, idx_test = \
    load_feature_construct_H_and_R(data_dir)
# set all vertex weights to 1.
# R[R != 0] = 1
G = hgut.generate_G_from_H(H, R, E_weights, Pi_version=cfg['Pi_version'])
n_class = int(Y.max() + 1)
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# transform data to device
fts = torch.Tensor(X).to(device)
lbls = torch.Tensor(Y).squeeze().long().to(device)
G = torch.Tensor(G).to(device)
idx_train = torch.Tensor(idx_train).long().to(device)
idx_test = torch.Tensor(idx_test).long().to(device)


def train_model(model, criterion, optimizer, scheduler, num_epochs=25, print_freq=500, seed=cfg['seed']):
    since = time.time()

    # set seed in training
    # Python random seed
    random.seed(seed)

    # NumPy random seed
    np.random.seed(seed)

    # PyTorch random seed
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)  # If you're using CUDA

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    for epoch in range(num_epochs):
        if epoch % print_freq == 0:
            print('-' * 10)
            print(f'Epoch {epoch}/{num_epochs - 1}')

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                scheduler.step()
                model.train()  # Set model to training mode
            else:
                model.eval()  # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0

            idx = idx_train if phase == 'train' else idx_test

            # Iterate over data.
            optimizer.zero_grad()
            with torch.set_grad_enabled(phase == 'train'):
                outputs = model(fts, G)
                loss = criterion(outputs[idx], lbls[idx])
                _, preds = torch.max(outputs, 1)

                # backward + optimize only if in training phase
                if phase == 'train':
                    loss.backward()
                    optimizer.step()

            # statistics
            running_loss += loss.item() * fts.size(0)
            running_corrects += torch.sum(preds[idx] == lbls.data[idx])

            epoch_loss = running_loss / len(idx)
            epoch_acc = running_corrects.double() / len(idx)

            if epoch % print_freq == 0:
                print(f'{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            # deep copy the model
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())

        if epoch % print_freq == 0:
            print(f'Best val Acc: {best_acc:4f}')
            print('-' * 20)

    time_elapsed = time.time() - since
    print(f'\nTraining complete in {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s')
    print(f'Best val Acc: {best_acc:4f}')

    # load best model weights
    model.load_state_dict(best_model_wts)
    return model


def _main():
    print('Class number:', n_class)
    print('Pi matrix version:', cfg['Pi_version'])
    print('Start training...')
    # print(f"Classification on {cfg['on_dataset']} dataset!!! class number: {n_class}")
    # print(f"use MVCNN feature: {cfg['use_mvcnn_feature']}")
    # print(f"use GVCNN feature: {cfg['use_gvcnn_feature']}")
    # print(f"use MVCNN feature for structure: {cfg['use_mvcnn_feature_for_structure']}")
    # print(f"use GVCNN feature for structure: {cfg['use_gvcnn_feature_for_structure']}")
    # print('Configuration -> Start')
    # pp.pprint(cfg)
    # print('Configuration -> End')
    
    model_ft = HGNN(in_ch=fts.shape[1],
                    n_class=n_class,
                    n_hid=cfg['n_hid'],
                    dropout=cfg['drop_out'])
    model_ft = model_ft.to(device)

    optimizer = optim.Adam(model_ft.parameters(), lr=cfg['lr'],
                           weight_decay=cfg['weight_decay'])
    # optimizer = optim.SGD(model_ft.parameters(), lr=0.01, weight_decay=cfg['weight_decay)
    schedular = optim.lr_scheduler.MultiStepLR(optimizer,
                                               milestones=cfg['milestones'],
                                               gamma=cfg['gamma'])
    criterion = torch.nn.CrossEntropyLoss()

    model_ft = train_model(model_ft, criterion, optimizer, schedular, cfg['max_epoch'], print_freq=cfg['print_freq'])


if __name__ == '__main__':
    _main()
