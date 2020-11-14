from argparse import ArgumentParser

parser=ArgumentParser()

# Global
parser.add_argument('--gpu', type=str, dest='gpu', default='0')

# For Meta-test
parser.add_argument('--inputpath', type=str, dest='inputpath', default='TestSet/Set5/g13/LR/')
parser.add_argument('--gtpath', type=str, dest='gtpath', default='TestSet/Set5/GT_crop/')
parser.add_argument('--kernelpath', type=str, dest='kernelpath', default='TestSet/Set5/g13/kernel.mat')
parser.add_argument('--savepath', type=str, dest='savepath', default='results/Set5')
parser.add_argument('--model', type=int, dest='model', choices=[0,1,2,3], default=0)
parser.add_argument('--num', type=int, dest='num_of_adaptation', choices=[1,10], default=1)

# For Meta-Training
parser.add_argument('--trial', type=int, dest='trial', default=0)
parser.add_argument('--step', type=int, dest='step', default=0)
parser.add_argument('--train', dest='is_train', default=False, action='store_true')

args= parser.parse_args()

IS_TRANSFER = True
TRANS_MODEL = 'Pretrained/Pretrained'

# Dataset Options
HEIGHT=64
WIDTH=64
CHANNEL=3

SCALE_LIST=[2.0]

META_ITER=10000
META_BATCH_SIZE=1
META_LR=1e-4

TASK_ITER=5
TASK_BATCH_SIZE=15
TASK_LR=1e-2

# Loading tfrecord and saving paths
TFRECORD_PATH='train_SR_MZSR.tfrecord'
CHECKPOINT_DIR='SR'