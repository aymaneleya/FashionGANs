import data_loader
from torch.utils.data import DataLoader
import os
from matplotlib import pyplot as plt
import torch
import GANs
import down_sample
from torch.autograd import Variable
import pickle
import numpy as np
from IPython.display import display, clear_output


cuda = torch.cuda.is_available()
torch.cuda.empty_cache()
device = torch.device("cuda:0" if cuda else "cpu")
X, y = None,None

# release
# if os.path.isfile(os.path.join(os.path.dirname(__file__),'..','data','data.pkl')):
#     with open(os.path.join(os.path.dirname(__file__),'..','data','data.pkl')) as handle:
#         X,y = pickle.load(handle)

# debug
loaded_data = None
# if os.path.isfile(os.path.join(os.path.dirname(__file__),'..','data','debug_data_10k.pkl')):
#     with open(os.path.join(os.path.dirname(__file__),'..','data','debug_data_10k.pkl'),'rb') as handle:
if os.path.isfile(os.path.join(os.path.dirname(__file__),'..','data','debug_data.pkl')):
    with open(os.path.join(os.path.dirname(__file__),'..','data','debug_data.pkl'),'rb') as handle:
        loaded_data = pickle.load(handle)
        X,y = loaded_data[0],loaded_data[1]
else:
    X, y = data_loader.load_data()
training_data = data_loader.FashionData(X,y,'train')
testing_data = data_loader.FashionData(X,y,'test')

batch_size = 50

train_loader = DataLoader(training_data, batch_size=batch_size,pin_memory=cuda)
test_loader  = DataLoader(testing_data, batch_size=batch_size, pin_memory=cuda)

flatten_image_size = 128*128

latent_dim_g2 = flatten_image_size + GANs.gausian_noise_size + GANs.human_attributes_size # 16492

G1 = GANs.Generator1()
D1 = GANs.Discriminator1()
if cuda:
    G1.cuda()
    D1.cuda()

loss = torch.nn.BCELoss()
print("Using device:", device)

generator_1_optim = torch.optim.Adam(G1.parameters(), 2e-3, betas=(0.5, 0.999))
discriminator_1_optim = torch.optim.Adam(D1.parameters(), 2e-3, betas=(0.5, 0.999))


tmp_img = "tmp_gan_out.png"
discriminator_loss, generator_loss = [], []

num_epochs = 50
for epoch in range(num_epochs):
    batch_d_loss, batch_g_loss = [], []
    
    for i , data in enumerate(train_loader, 0):
        
        d, mS0, S0, label = data
        
        true_label = torch.ones(batch_size, 1).to(device)
        fake_label = torch.zeros(batch_size, 1).to(device)
        
        G1.zero_grad()

        ### Train the G
        z = torch.randn(batch_size, 100,dtype=torch.float64)
        dz = torch.cat([d, z] , dim=1)
        dz = dz.view((batch_size,dz.shape[1],1,1))
        dz = Variable(dz).to(device,dtype=torch.float)
        x_g_mS0 = Variable(mS0).to(device,dtype=torch.float)

        S_tilde = G1.forward(dz,x_g_mS0)

        mS_tilde = down_sample.get_segmented_image_7_s_tilde(batch_size, S_tilde)
        x_fake_mS = down_sample.get_downsampled_image_4_mS0(batch_size, mS_tilde)
        x_fake_mS = Variable(x_fake_mS).to(device,dtype=torch.float)
        x_fake_d = Variable(d).to(device,dtype=torch.float) 
        output = D1.forward(S_tilde,x_fake_mS,x_fake_d)

        error_true = loss(output, true_label) 
        error_true.backward()
        generator_1_optim.step()        
        D1.zero_grad()

        ### Train the Discriminator with valid labels        
        x_true_S0 = Variable(S0).to(device,dtype=torch.float)
        x_true_mS0 = Variable(mS0).to(device,dtype=torch.float)
        x_true_d = Variable(d).to(device,dtype=torch.float)        
        output = D1.forward(x_true_S0,x_true_mS0,x_true_d)
        
        true_loss = loss(output, true_label) 
        # error_true.backward()
        # discriminator_1_optim.step()
        # D1.zero_grad()

        ### Train the Discriminator with fake labels
        x_notmatch_d = x_true_d[torch.randperm(x_true_d.size()[0])]        
        x_notmatch_d = Variable(x_notmatch_d).to(device)    
        output = D1.forward(x_true_S0 ,x_true_mS0,x_notmatch_d)

        notmatch_loss = loss(output, fake_label) 
        # error_notmatch.backward()
        # discriminator_1_optim.step()
        # D1.zero_grad()

        ### Train the Discriminator with generated images
        output = D1.forward(S_tilde.detach(),x_fake_mS.detach(),x_fake_d)
        generated_image_loss = loss(output, fake_label) 

        overall_loss = (true_loss + notmatch_loss + generated_image_loss)/3
        overall_loss.backward()
        discriminator_1_optim.step()

        batch_d_loss.append(overall_loss)
        batch_g_loss.append(error_true)

    discriminator_loss.append(np.mean(batch_d_loss))
    generator_loss.append(np.mean(batch_g_loss))

    print('Training epoch %d: discriminator_loss = %.5f, generator_loss = %.5f' % (epoch, discriminator_loss[epoch].item(), generator_loss[epoch].item()))


