from __future__ import print_function
import argparse
import torch
import torch.nn.functional as F
from torchvision import datasets, transforms
from models import vgg, resnet, densenet
import numpy as np
import os
import sys
from tqdm import tqdm
from utils import *
import glob

if __name__ == '__main__':


	parser = argparse.ArgumentParser(description='Cifar10 Evaluation')
	parser.add_argument('--cp-path', type=str, default=None, metavar='Path', help='Path for cps')
	parser.add_argument('--data-path', type=str, default='./data/', metavar='Path', help='Path to data')
	parser.add_argument('--batch-size', type=int, default=100, metavar='N', help='input batch size for testing (default: 100)')
	parser.add_argument('--model', choices=['vgg', 'resnet', 'densenet'], default='resnet')
	parser.add_argument('--no-cuda', action='store_true', default=False, help='Disables GPU use')
	parser.add_argument('--workers', type=int, default=4, metavar='N', help='Data load workers (default: 4)')
	args = parser.parse_args()
	args.cuda = True if not args.no_cuda and torch.cuda.is_available() else False

	transform_test = transforms.Compose([transforms.ToTensor(), transforms.Normalize([x / 255 for x in [125.3, 123.0, 113.9]], [x / 255 for x in [63.0, 62.1, 66.7]])])
	testset = datasets.CIFAR10(root='./data', train=False, download=True, transform=transform_test)
	test_loader = torch.utils.data.DataLoader(testset, batch_size=args.batch_size, shuffle=False, num_workers=args.workers)

	cp_list = glob.glob(args.cp_path+'*.pt')

	best_model, best_acc = None, -float('inf')

	for cp in cp_list:

		ckpt = torch.load(cp, map_location = lambda storage, loc: storage)
		softmax = get_sm_from_cp(ckpt)

		if args.model == 'vgg':
			model = vgg.VGG('VGG16', sm_type=softmax)
		elif args.model == 'resnet':
			model = resnet.ResNet18(sm_type=softmax)
		elif args.model == 'densenet':
			model = densenet.densenet_cifar(sm_type=softmax)
		
		try:
			model.load_state_dict(ckpt['model_state'], strict=True)
		except RuntimeError as err:
			print("Runtime Error: {0}".format(err))
		except:
			print("Unexpected error:", sys.exc_info()[0])
			raise

		if args.cuda:
			device = get_freer_gpu()
			model = model.cuda(device)

		model.eval()

		correct = 0

		with torch.no_grad():

			iterator = tqdm(test_loader, total=len(test_loader))
			for batch in iterator:

				x, y = batch

				x = x.to(device)
				y = y.to(device)

				embeddings = model.forward(x)

				embeddings_norm = F.normalize(embeddings, p=2, dim=1)

				out = model.out_proj(embeddings_norm, y)

				pred = F.softmax(out, dim=1).max(1)[1].long()
				correct += pred.squeeze().eq(y.squeeze()).detach().sum().item()

		acc = 100.*correct/len(testset)
		model_id = cp.split('/')[-1]

		print('\nAccuracy of model {}: {}'.format(model_id, acc))

		if acc>best_acc:
			best_model, best_acc = model_id, acc

	print('Best model and corresponding ACC: {} - {}'.format(best_model, best_acc))
