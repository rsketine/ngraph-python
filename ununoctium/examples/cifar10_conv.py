#!/usr/bin/env python
# ----------------------------------------------------------------------------
# Copyright 2015-2016 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""
Small CIFAR10 based convolutional neural network. Showcases the use of cost
scaling with the fp16 data format.
"""

import numpy as np
from geon.backends.graph.graphneon import *
from neon import logger as neon_logger


# parse the command line arguments
parser = NeonArgparser(__doc__)
parser.add_argument('--subset_pct', type=float, default=100,
                    help='subset of training dataset to use (percentage)')
args = parser.parse_args()

# setup data provider
imgset_options = dict(inner_size=32, scale_range=40, aspect_ratio=110,
                      repo_dir=args.data_dir, subset_pct=args.subset_pct)
train = ImageLoader(set_name='train', shuffle=True, do_transforms=True, **imgset_options)
test = ImageLoader(set_name='validation', shuffle=False, do_transforms=False, **imgset_options)

# hyperparameters
if args.datatype in [np.float16]:
    cost_scale = 10.
num_epochs = args.epochs

#TODO Switch to momentum
init_uni = Uniform(low=-0.1, high=0.1)
if args.datatype in [np.float32, np.float64]:
    opt_gdm = GradientDescentMomentum(learning_rate=0.01,
                                      momentum_coef=0.9,
                                      stochastic_round=args.rounding)
elif args.datatype in [np.float16]:
    opt_gdm = GradientDescentMomentum(learning_rate=0.01 / cost_scale,
                                      momentum_coef=0.9,
                                      stochastic_round=args.rounding)

bn = True
layers = [Conv((5, 5, 16), init=init_uni, activation=Rectlin(), batch_norm=bn),
          Pooling((2, 2)),
          Conv((5, 5, 32), init=init_uni, activation=Rectlin(), batch_norm=bn),
          Pooling((2, 2)),
          Affine(nout=500, init=init_uni, activation=Rectlin(), batch_norm=bn),
          Affine(nout=10, init=init_uni, activation=Softmax())]

if args.datatype in [np.float32, np.float64]:
    cost = GeneralizedCost(costfunc=CrossEntropyMulti())
elif args.datatype in [np.float16]:
    cost = GeneralizedCost(costfunc=CrossEntropyMulti(scale=cost_scale))

model = Model(layers=layers)

# configure callbacks
callbacks = Callbacks(model, eval_set=test, **args.callback_args)

model.fit(train, optimizer=opt_gdm, num_epochs=num_epochs,
          cost=cost, callbacks=callbacks)

error_rate = model.eval(test, metric=Misclassification())
neon_logger.display('Misclassification error = %.1f%%' % (error_rate * 100))