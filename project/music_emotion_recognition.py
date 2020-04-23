# -*- coding: utf-8 -*-
# # Initialization

# ## Imports

# +
import numpy as np
import scipy as sp
import pandas as pd
import librosa
import matplotlib.pyplot as plt

import sklearn.model_selection
import sklearn.linear_model
import sklearn.svm
import sklearn.neighbors
import sklearn.feature_selection

from tqdm.notebook import tqdm
from functools import lru_cache
from zipfile import ZipFile

import os
import requests
import shutil
import inspect
# -

# ## Download Dataset

# +
DW_URL  = "https://polimi365-my.sharepoint.com/:u:/g/personal/10768481_polimi_it/ET_EMOV_tgBAm2yIQn4m4h0B8FxvxcDCJkpedf_3SRtLWw?download=1"
DW_PATH = "./dataset.zip"

if os.path.isdir(DW_PATH[:-4]):
    print("already downloaded.")
else:
    print("downloading...")
    with requests.get(DW_URL, stream=True) as r:
        with open(DW_PATH, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    print("unzipping...")
    with ZipFile(DW_PATH) as z:
        z.extractall()
    os.unlink(DW_PATH)
    print("DONE!")
# -

# ## Other stuff

# +
RUNTIME_DIR = "./run/"

try:
    os.mkdir(RUNTIME_DIR)
except FileExistsError:
    pass
# -

# # Model

# ## Extract Features

DATASET_PATH = "./dataset/"

# Names of relevant features

# +
# for librosa
features_to_extract = {
    "feature": ["spectral_flatness", "tonnetz", "tempogram"],
    "effects": ["harmonic", "percussive"],
    "beat": ["beat_track"]
}

# filter from dataset
features_to_select = [
    "F0final",
    "RMSenergy",
    "zcr",
    "spectralRollOff",
    "spectralFlux",
    "spectralCentroid",
    "spectralEntropy",
    "spectralVariance",
    "spectralSkewness",
    "spectralKurtosis",
    "spectralSlope",
    "psySharpness",
    "spectralHarmonicity",
    "mfcc",
]


# -

# ### Extract features using librosa

# +
@lru_cache(maxsize=None)
def new_extract_features(track_id):
    """returns a pandas series of extracted features for track `track_id`"""
    path = os.path.join(DATASET_PATH, "audio", f"{track_id}.mp3")
    y, sr = librosa.load(path, duration=60)
    features = dict()
    f_len = len([x for y in features_to_extract.values() for x in y])
    with tqdm(total=f_len) as pbar:
        for tp in features_to_extract.keys():
            for feat in features_to_extract[tp]:
                pbar.update()
                features[feat] = librosa.__getattribute__(tp).__getattribute__(feat)(y=y)
    # TODO: extract mean/std to a pandas series
    return features

def extract_features(track_id): # to make everything else working in the meanwhile
    sr = pd.Series(dtype="float64")
    sr.name = track_id
    return sr

def get_extracted_features(track_id):
    # hash features to extract and function code to invalidate cache
    h = hex(hash((hash(inspect.getsource(extract_features)), hash(repr(features_to_extract)))))[-6:]
    cache_path = os.path.join(RUNTIME_DIR, f"lrosa_features@{h}.csv")
    ## open cached file or create a new DataFrame
    try:
        with open(cache_path) as fin:
            features = pd.read_csv(fin, header=0, index_col=0, sep=",", engine="c")
    except FileNotFoundError:
        features = pd.DataFrame()
    ## select features for selected track_id
    if not track_id in features.index:
        features[track_id] = extract_features(track_id)
        with open(cache_path,"w") as fout:
            features.to_csv(fout)
    return features[track_id]


# -

new_extract_features(10)["spectral_flatness"].shape


# ### Load provided features

# +
@lru_cache(maxsize=None)
def get_frame_level_features(track_id):
    """returns a pandas matrix of all frame-level features for `track_id`"""
    with open(os.path.join(DATASET_PATH, "features", f"{track_id}.csv")) as fin:
        return pd.read_csv(fin, header=0, index_col=0, sep=";", engine="c")

def get_clip_level_features(track_id):
    """converts frame-level features to relevant clip-level features"""
    # just mean everything for now (except deltas), might be redefined later in the notebook
    sr = get_frame_level_features(track_id).mean()
    sr.name = track_id
    return sr.loc[filter(lambda c: not "_sma_de" in c and any((f in c for f in features_to_select)), sr.index)]

def get_features(selected_tracks=None, length=None):
    """iterates over the dataset and return a pandas matrix of features for all/selected tracks"""
    if selected_tracks is None:
        track_files = os.listdir(os.path.join(DATASET_PATH, "features/"))
        selected_tracks = sorted(map(lambda name: int(name.split(".")[0]), track_files))[:length]
    all_feats = (
        pd.concat((get_clip_level_features(track_id), get_extracted_features(track_id)))
        for track_id in tqdm(selected_tracks, leave=False)
    )
    # NB: the upper limit is set because we are only interested to the `2-2000` range.
    return pd.DataFrame(all_feats).loc[:2000]
# -

get_features(length=50)

# ## Extract Annotations

def get_annotations(length=None):
    """returns a pandas matrix of all the annotations of all tracks"""
    with open(os.path.join(DATASET_PATH, "annotations.csv")) as fin:
        return pd.read_csv(fin, header=0, index_col=0, sep=",\s*", engine="python").iloc[:length]

get_annotations(50)


# ## Feature Visualization

def get_clip_level_features(track_id):
    """converts frame-level features to relevant clip-level features"""
    # just mean everything for now (except deltas), might be redefined later in the notebook
    sr = get_frame_level_features(track_id).mean()
    sr.name = track_id
    return sr.loc[filter(lambda c: not "_sma_de" in c, sr.index)]


# ### Annotations splitting

# +
maxs = dict()
mins = dict()

for label in get_annotations().columns:
    annot = get_annotations().loc[:, label]
    maxs[label] = annot.loc[annot >= annot.mean()].sort_values(ascending=False).index
    mins[label] = annot.loc[annot < annot.mean()].sort_values(ascending=True).index


# -

# ### Helper functions

# +
def plot_feature_evolution(tracks, feature_name, time_slice=slice(None)):
    data = pd.concat((
        get_frame_level_features(i).loc[time_slice, feature_name]
        for i in tqdm(tracks, leave=False)
        ), axis=1)
    plt.xlabel("time")
    plt.ylabel(feature_name)
    plt.plot(data)

def plot_feature_distribution(tracks, feature_name, x_axis=None):
    mean_std = get_features(sorted(tracks)).loc[:, [f"{feature_name}_amean", f"{feature_name}_stddev"]]
    up = mean_std.loc[:, f"{feature_name}_amean"].max() + mean_std.loc[:, f"{feature_name}_stddev"].max()
    low = mean_std.loc[:, f"{feature_name}_amean"].min() - mean_std.loc[:, f"{feature_name}_stddev"].max()
    if x_axis is None:
        x_axis = np.linspace(low, up, 100)
    dists = mean_std.apply(lambda row: sp.stats.norm(row[0], row[1]).pdf(x_axis), axis=1, result_type="expand").T
    dists.index = x_axis
    plt.xlabel(feature_name)
    plt.ylabel("p.d.f.")
    plt.plot(dists)


# -

# Functions for plotting feature-distribution for VA mean values.

def plot_va_means_distributions(feature_name, n_tracks, x_axis=None):
    plt.figure(figsize=(15,10))
    i = 1
    with tqdm(total=4, leave=False) as pbar:
        for label in ["valence_mean", "arousal_mean"]:
            plt.subplot(2,2,i*2-1)
            plt.title(f"tracks with min. {label}")
            plot_feature_distribution(mins[label][:n_tracks], feature_name, x_axis)
            pbar.update()
            plt.subplot(2,2,i*2)
            plt.title(f"tracks with max. {label}")
            plot_feature_distribution(maxs[label][:n_tracks], feature_name, x_axis)
            pbar.update()
            i += 1
    plt.savefig(os.path.join(RUNTIME_DIR, f"{feature_name}-dists.pdf"))


# Functions for plotting feature time-evolution for VA mean values.

def plot_va_means_evolution(feature_name, n_tracks, time_slice=slice(10,50)):
    plt.figure(figsize=(15,10))
    i = 1
    with tqdm(total=4, leave=False) as pbar:
        for label in ["valence_mean", "arousal_mean"]:
            plt.subplot(2,2,i*2-1)
            plt.title(f"tracks with min. {label}")
            plot_feature_evolution(mins[label][:n_tracks], feature_name, time_slice)
            pbar.update()
            plt.subplot(2,2,i*2)
            plt.title(f"tracks with max. {label}")
            plot_feature_evolution(maxs[label][:n_tracks], feature_name, time_slice)
            pbar.update()
            i += 1
    plt.savefig(os.path.join(RUNTIME_DIR, f"{feature_name}-time.pdf"))


# ### Feature names

with open("features.txt") as fin:
    print(fin.read())

# ### Feature distributions

plot_va_means_distributions("pcm_RMSenergy_sma", 100, np.linspace(0, 0.4, 100))

plot_va_means_distributions("F0final_sma", 20, np.linspace(0, 500, 100))

plot_va_means_distributions("pcm_fftMag_psySharpness_sma", 50, np.linspace(0, 2.5, 100))

plot_va_means_distributions("pcm_fftMag_spectralHarmonicity_sma", 100, np.linspace(0,3,100))

plot_va_means_distributions("pcm_zcr_sma", 100, np.linspace(0, 0.25, 100))

# ### Feature time-evolution

plot_va_means_evolution("pcm_zcr_sma_amean", 10)

# # Regression

# ## Preliminary manual feature selection

# +
relevant_features = ["zcr", "F0final", "mfcc", "spectralHarmonicity", "psySharpness", "spectralRollOff"]
relevant_moments = ["mean"] # provide pandas function names

def get_clip_level_features(track_id):
    """converts frame-level features to relevant clip-level features"""
    flf = get_frame_level_features(track_id)
    feats = list()
    for func in relevant_moments:
        feat = flf.__getattribute__(func)()
        feat.index = map(lambda i: f"{i}__{func}", feat.index)
        feats.append(feat)
    sr = pd.concat(feats)
    sr.name = track_id
    return sr.loc[filter(lambda f: any((x in f for x in relevant_features)), sr.index)]
    return sr


# -

# ## Preparation

# Common procedure for regression training, testing, and cross-validation.

# +
def run_regression(reg, feats_train, feats_test, annots_train, feat_selector):
    predictions = pd.DataFrame()
    for label in annots_train.columns:
        selected_feats_train = feat_selector[label].transform(feats_train)
        selected_feats_test  = feat_selector[label].transform(feats_test)
        # regression fitting
        reg = reg.fit(selected_feats_train, annots_train.loc[:, label])
        # regression prediction
        pred = pd.Series(reg.predict(selected_feats_test), feats_test.index)
        pred.name = label
        predictions = predictions.join(pred, how="right")
    return predictions

def run_cross_validation(reg):
    pass #TODO
# -

# Extract N tracks from the dataset.

N       = 2000
feats   = get_features(length=N)
annots  = get_annotations(length=N)
print(f"shape of feats: {feats.shape}\nshape of annots: {annots.shape}")

# Filter features using k-best.

# +
feat_selector = dict()
k_best = 50

for label in annots.columns:
    feat_selector[label] = sklearn.feature_selection.SelectKBest(k=k_best).fit(feats, annots.loc[:, label])
# -

# Split the dataset in training set and testing set.

# +
(feats_train, feats_test,
 annots_train, annots_test) = sklearn.model_selection.train_test_split(feats, annots)

print("Training set:", feats_train.index)
print("Testing set:", feats_test.index)
# -

# Normalize training dataset to have $\bar{X}=0$ and $\sigma_X=1$:

feats_m, feats_std = feats_train.mean(), feats_train.std()
feats_train = (feats_train-feats_m)/feats_std
feats_test  = (feats_test-feats_m)/feats_std

# ## Linear Regression

lin_reg = sklearn.linear_model.LinearRegression()
linear_predictions = run_regression(lin_reg, feats_train, feats_test, annots_train, feat_selector)
linear_predictions

# ## SVM Regression

svm_reg = sklearn.svm.SVR()
svm_predictions = run_regression(svm_reg, feats_train, feats_test, annots_train, feat_selector)
svm_predictions

# ## KN Regression

kn_reg = sklearn.neighbors.KNeighborsRegressor(10, "distance")
kn_predictions = run_regression(kn_reg, feats_train, feats_test, annots_train, feat_selector)
kn_predictions


# # Evaluation

def get_metrics(prediction, ground_truth):
    print("MSE:     ", sklearn.metrics.mean_squared_error(ground_truth, prediction))
    print("R² score:", sklearn.metrics.r2_score(ground_truth, prediction))


# ## Metrics for Linear regression

for label in annots.columns:
    print(f"=== metrics for {label} ===")
    get_metrics(linear_predictions.loc[:, label], annots_test.loc[:, label])
    print()

# ## Metrics for SVM regression

for label in annots.columns:
    print(f"=== metrics for {label} ===")
    get_metrics(svm_predictions.loc[:, label], annots_test.loc[:, label])
    print()

# ## Metrics for KN regression

for label in annots.columns:
    print(f"=== metrics for {label} ===")
    get_metrics(kn_predictions.loc[:, label], annots_test.loc[:, label])
    print()
