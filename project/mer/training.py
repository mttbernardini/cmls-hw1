from functools import lru_cache
from tqdm import tqdm
from sklearn import linear_model

import numpy as np
import scipy as sp

from . import model

def train_reg():
	# silly example to try
	l = 10
	feats   = model.get_all_features(l)
	arousal = model.get_all_arousal(l)
	valence = model.get_all_valence(l)
	## normalization
	feats_m, feats_std = feats.mean(), feats.std()
	feats_norm = (feats-feats_m)/feats_std
	## regressor fitting
	a_reg = linear_model.LinearRegression()
	a_reg.fit(feats_norm, arousal.loc[:, "arousal_mean"])
	return (feats_m, feats_std, a_reg)