

import world
import torch
from dataloader import BasicDataset
from torch import nn
import numpy as np
from DNN import DNN_for_feature_extra
from sklearn.decomposition import PCA


class BasicModel(nn.Module):    
    def __init__(self):
        super(BasicModel, self).__init__()
    
    def getUsersRating(self, users):
        raise NotImplementedError
    
class PairWiseModel(BasicModel):
    def __init__(self):
        super(PairWiseModel, self).__init__()
    def bpr_loss(self, users, pos, neg):
        
        raise NotImplementedError
    
class PureMF(BasicModel):
    def __init__(self, 
                 config:dict, 
                 dataset:BasicDataset):
        super(PureMF, self).__init__()
        self.num_users  = dataset.n_users
        self.num_items  = dataset.m_items
        self.latent_dim = config['latent_dim_rec']
        self.f = nn.Sigmoid()
        self.__init_weight()
        
    def __init_weight(self):
        self.embedding_user = torch.nn.Embedding(
            num_embeddings=self.num_users, embedding_dim=self.latent_dim)
        self.embedding_item = torch.nn.Embedding(
            num_embeddings=self.num_items, embedding_dim=self.latent_dim)
        print("using Normal distribution N(0,1) initialization for PureMF")
        
    def getUsersRating(self, users):
        users = users.long()
        users_emb = self.embedding_user(users)
        items_emb = self.embedding_item.weight
        scores = torch.matmul(users_emb, items_emb.t())
        return self.f(scores)
    
    def bpr_loss(self, users, pos, neg):
        users_emb = self.embedding_user(users.long())
        pos_emb   = self.embedding_item(pos.long())
        neg_emb   = self.embedding_item(neg.long())
        pos_scores= torch.sum(users_emb*pos_emb, dim=1)
        neg_scores= torch.sum(users_emb*neg_emb, dim=1)
        loss = torch.mean(nn.functional.softplus(neg_scores - pos_scores))
        reg_loss = (1/2)*(users_emb.norm(2).pow(2) + 
                          pos_emb.norm(2).pow(2) + 
                          neg_emb.norm(2).pow(2))/float(len(users))
        return loss, reg_loss
        
    def forward(self, users, items):
        users = users.long()
        items = items.long()
        users_emb = self.embedding_user(users)
        items_emb = self.embedding_item(items)
        scores = torch.sum(users_emb*items_emb, dim=1)
        return self.f(scores)

class LightGCN(BasicModel):
    def __init__(self, 
                 config:dict, 
                 dataset:BasicDataset):
        super(LightGCN, self).__init__()
        self.config = config
        self.dataset : dataloader.BasicDataset = dataset
        self.__init_weight()
        self.DNN = DNN_for_feature_extra()
        # self.DNN_drug_adj = DNN_for_drug_adj()
        # self.DNN_food_adj = DNN_for_food_adj()
        # config_atten = {
        #     "num_of_attention_heads": 2,
        #     "hidden_size": 64
        #  }
        # self.SelfAttention = SelfAttention(config_atten)

    def get_feature_extra(self):
        # Dynamically locate feature files based on active dataset
        import world as _world
        dataset_name = _world.dataset
        feat_dir = f'../data/{dataset_name}/feature_extra/'

        # Discover file names (any .txt in the feature_extra directory)
        import os, glob
        txt_files = sorted(glob.glob(feat_dir + '*.txt'))
        if len(txt_files) < 2:
            raise FileNotFoundError(
                f"Expected at least 2 feature files in {feat_dir}, found: {txt_files}")

        # Convention: first file = drug features, second = food features
        drug_feat_path = [p for p in txt_files if 'drug' in os.path.basename(p).lower()]
        food_feat_path = [p for p in txt_files if 'food' in os.path.basename(p).lower()]
        if not drug_feat_path or not food_feat_path:
            drug_feat_path = [txt_files[0]]
            food_feat_path = [txt_files[1]]
        drug_feat_path = drug_feat_path[0]
        food_feat_path = food_feat_path[0]

        print(f"load_feature...\n  drug: {drug_feat_path}\n  food: {food_feat_path}")

        def _load_feat(path):
            npy_path = path.replace('.txt', '.npy')
            if os.path.exists(npy_path):
                print(f"    loading {os.path.basename(npy_path)} (numpy binary)...")
                return np.load(npy_path).astype(np.float32)
            print(f"    reading {path} (text) ...")
            return np.loadtxt(path, dtype=np.float32)

        d_feat_extra = torch.Tensor(_load_feat(drug_feat_path)).to(world.device)
        f_feat_extra = torch.Tensor(_load_feat(food_feat_path)).to(world.device)

        # drug_food_adj = np.zeros((143,213),dtype=float)
        # with open('../data/DFI_drugbank/train.txt') as f:
        #     for l in f.readlines():
        #         if len(l) > 0:
        #             l = l.strip(' \n').split(' ')
        #             items = [int(i) for i in l[1:]]
        #             uid = int(l[0])
        #             for i in range(len(items)):
        #                 drug_food_adj[uid][items[i]] = 1.0
        # food_drug_adj = np.transpose(drug_food_adj)
        # print(food_drug_adj.shape)
        
        # drug_adj = torch.Tensor(drug_food_adj).to(world.device)
        # food_adj = torch.Tensor(food_drug_adj).to(world.device)
       
        return d_feat_extra,f_feat_extra

    def __init_weight(self):
        self.num_users  = self.dataset.n_users
        self.num_items  = self.dataset.m_items
        self.latent_dim = self.config['latent_dim_rec']
        self.n_layers = self.config['lightGCN_n_layers']
        self.keep_prob = self.config['keep_prob']
        self.A_split = self.config['A_split']
        self.embedding_user = torch.nn.Embedding(
            num_embeddings=self.num_users, embedding_dim=self.latent_dim)
        self.embedding_item = torch.nn.Embedding(
            num_embeddings=self.num_items, embedding_dim=self.latent_dim)
        if self.config['pretrain'] == 0:
#             nn.init.xavier_uniform_(self.embedding_user.weight, gain=1)
#             nn.init.xavier_uniform_(self.embedding_item.weight, gain=1)
#             print('use xavier initilizer')
# random normal init seems to be a better choice when lightGCN actually don't use any non-linear activation function
            nn.init.normal_(self.embedding_user.weight, std=0.1)
            nn.init.normal_(self.embedding_item.weight, std=0.1)
            world.cprint('use NORMAL distribution initilizer')
        else:
            self.embedding_user.weight.data.copy_(torch.from_numpy(self.config['user_emb']))
            self.embedding_item.weight.data.copy_(torch.from_numpy(self.config['item_emb']))
            print('use pretarined data')
        self.f = nn.Sigmoid()
        self.Graph = self.dataset.getSparseGraph()
        print(f"lgn is already to go(dropout:{self.config['dropout']})")

        self.drug_feature_extra, self.food_feature_extra = self.get_feature_extra()

        # print("save_txt")
    def __dropout_x(self, x, keep_prob):
        size = x.size()
        index = x.indices().t()
        values = x.values()
        random_index = torch.rand(len(values)) + keep_prob
        random_index = random_index.int().bool()
        index = index[random_index]
        values = values[random_index]/keep_prob
        g = torch.sparse.FloatTensor(index.t(), values, size)
        return g
    
    def __dropout(self, keep_prob):
        if self.A_split:
            graph = []
            for g in self.Graph:
                graph.append(self.__dropout_x(g, keep_prob))
        else:
            graph = self.__dropout_x(self.Graph, keep_prob)
        return graph
    
    def computer(self):
        """
        LightGCN graph propagation only.
        Returns raw GCN embeddings for all users and items (no DNN).
        """
        users_emb = self.embedding_user.weight
        items_emb = self.embedding_item.weight
        all_emb = torch.cat([users_emb, items_emb])
        embs = [all_emb]
        if self.config['dropout']:
            if self.training:
                print("droping")
                g_droped = self.__dropout(self.keep_prob)
            else:
                g_droped = self.Graph
        else:
            g_droped = self.Graph

        for layer in range(self.n_layers):
            if self.A_split:
                temp_emb = []
                for f in range(len(g_droped)):
                    temp_emb.append(torch.sparse.mm(g_droped[f], all_emb))
                side_emb = torch.cat(temp_emb, dim=0)
                all_emb = side_emb
            else:
                all_emb = torch.sparse.mm(g_droped, all_emb)
            embs.append(all_emb)
        embs = torch.stack(embs, dim=1)
        light_out = torch.mean(embs, dim=1)
        users, items = torch.split(light_out, [self.num_users, self.num_items])
        return users, items

    def getUsersRating(self, users):
        """
        Eval: compute full embeddings for ALL entities, rate all foods per batch.
        DNN is run once on full feature matrices (testbatch=5000 ensures single call).
        """
        gcn_users, gcn_items = self.computer()
        user_feat_extra = self.DNN(self.drug_feature_extra)
        item_feat_extra = self.DNN(self.food_feature_extra)
        all_users = torch.cat((gcn_users, user_feat_extra), 1)
        all_items = torch.cat((gcn_items, item_feat_extra), 1)
        users_emb = all_users[users.long()]
        items_emb = all_items
        rating = self.f(torch.matmul(users_emb, items_emb.t()))
        return rating

    def getEmbedding(self, users, pos_items, neg_items):
        """
        Training: DNN is run only on the batch entities (512 instead of 5000+1894).
        ~4.5x cheaper than running on all entities every batch.
        """
        gcn_users, gcn_items = self.computer()
        gcn_u  = gcn_users[users]
        gcn_pi = gcn_items[pos_items]
        gcn_ni = gcn_items[neg_items]
        # DNN on batch-specific features only
        u_feat  = self.DNN(self.drug_feature_extra[users])
        pi_feat = self.DNN(self.food_feature_extra[pos_items])
        ni_feat = self.DNN(self.food_feature_extra[neg_items])
        users_emb = torch.cat((gcn_u,  u_feat),  1)
        pos_emb   = torch.cat((gcn_pi, pi_feat), 1)
        neg_emb   = torch.cat((gcn_ni, ni_feat), 1)
        users_emb_ego = self.embedding_user(users)
        pos_emb_ego   = self.embedding_item(pos_items)
        neg_emb_ego   = self.embedding_item(neg_items)
        return users_emb, pos_emb, neg_emb, users_emb_ego, pos_emb_ego, neg_emb_ego
    
    def bpr_loss(self, users, pos, neg):
        (users_emb, pos_emb, neg_emb, 
        userEmb0,  posEmb0, negEmb0) = self.getEmbedding(users.long(), pos.long(), neg.long())
        reg_loss = (1/2)*(userEmb0.norm(2).pow(2) + 
                         posEmb0.norm(2).pow(2)  +
                         negEmb0.norm(2).pow(2))/float(len(users))
        pos_scores = torch.mul(users_emb, pos_emb)
        pos_scores = torch.sum(pos_scores, dim=1)
        neg_scores = torch.mul(users_emb, neg_emb)
        neg_scores = torch.sum(neg_scores, dim=1)
        
        loss = torch.mean(torch.nn.functional.softplus(neg_scores - pos_scores))
        
        return loss, reg_loss
    
    # def forward(self, users, items):
    #     # compute embedding
    #     all_users, all_items = self.computer()
    #     print(all_users)
    #     drug_feature_extra,food_feature_extra = self.get_feature_extra()
    #     print('forward')
    #     #all_users, all_items = self.computer()
    #     users_emb = all_users[users]
    #     items_emb = all_items[items]
    #     user_feat_extra = self.DNN(drug_feat_extra[users][:])
    #     item_feat_extra = self.DNN(food_feat_extra[items][:])
    #     users_emb_new = torch.cat(users_emb,user_feat_extra)
    #     items_emb_new = torch.cat(items_emb,item_feat_extra)
    #     inner_pro = torch.mul(users_emb_new, items_emb_new)
    #     gamma     = torch.sum(inner_pro, dim=1)
    #     return gamma
