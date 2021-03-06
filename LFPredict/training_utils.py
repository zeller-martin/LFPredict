import time
import tensorflow as tf
from tensorflow import keras
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy import stats
from .benchmark import estimate_phase_hilbert

class DataGenerator(keras.utils.Sequence) :
    '''
    Generator to supply LFDeep models with training or validation data
    
    Positional arguments for __init__:
    x_files -- list, paths to binary files (float32), which contain input data
    y_files -- list or list of lists, paths to binary files (float32), which contain output data
    batch_size -- int, number of training examples in a batch
    batches_per_epoch -- int, number of batches per epoch
    size -- int, number of samples to predict from
    
    Keyword arguments for __init__:
    memmap -- bool, whether to use memmap instead of array for large datasets (default: False)
    y_offset -- int, a known system delay to enhance instantaneous predictions (default: 0).
                Example: if new data is acquired with a constant delay of 10 ms at a sampling rate of 1 kHz, y_offset = 10 could improve real-time performance
    preprocessing_callback -- function, to be applied to training data snippets, to mimic processing steps such as filtering
    '''
    
    
    def _nest_inputs(self):
        if isinstance(self.y_files, tuple):
            self.y_files = list(self.y_files)
        if not any(isinstance(i, list) for i in self.y_files):
            self.y_files = [self.y_files]
            self._multiple_y = False
        else:
            self._multiple_y = True
    
    def _check_valid_input(self):
        error_msg = 'Unequal length of x_files and elements in y_files!'
        for y in self.y_files:
            assert self._n_files == len(y), error_msg
    
    def _number_of_samples(self, file, bytes_per_sample = 4):
        return os.path.getsize(file) // 4
    
    def _create_index_map(self):
        self._file_lengths = np.zeros( self._n_files )
        
        for i, x_f in enumerate(self.x_files):
            self._file_lengths[i] = self._number_of_samples(x_f)
            for y_list in self.y_files:
                assert self._file_lengths[i] == self._number_of_samples(y_list[i]), 'file length mismatch'
        
        self._total_samples = np.sum(self._file_lengths) - self._n_files * (self.size + self.y_offset)
        self._total_samples = int(self._total_samples)
        self._file_indices = np.zeros( self._total_samples )
        self._samples = np.zeros( self._total_samples )
        
        j = 0
        for i, file_len in enumerate(self._file_lengths):
            valid_indices = int(file_len - self.size - self.y_offset)
            self._file_indices[j : j + valid_indices] = i
            self._samples[j : j + valid_indices] = np.arange(valid_indices)
            j += valid_indices
            
        self._file_indices = self._file_indices.astype(int)
        self._samples = self._samples.astype(int)
    
    def _load_np_array(self, file):
        return np.fromfile(file, dtype = np.float32)
    
    def _load_memmap(self, file):
        return np.memmap(file, dtype = np.float32)
    
    def _load_data(self):
        if self.memmap:
            loading_func = self._load_memmap
        else:
            loading_func = self._load_np_array

        for i, x_f in enumerate(self.x_files):
            self.x_data.append( loading_func(x_f) )
            for j in range(self._n_outputs):
                self.y_data[j].append( loading_func(self.y_files[j][i] ))
    
    def _identity_preprocessing_callback(self, x):
        return x
    
    def __init__(self,
                 x_files, y_files,
                 batch_size, batches_per_epoch, size,
                 memmap = False,
                 y_offset = 0,
                 preprocessing_callback = None):
        
        self.x_files = x_files
        self.y_files = y_files
        self._n_files = len(self.x_files)
        
        self._nest_inputs()
        self._n_outputs = len(self.y_files)
        self._check_valid_input()
        
        
        self.x_data = list()
        self.y_data = [list() for i in range(len(self.y_files))]
        
        self.batch_size = batch_size
        self.batches_per_epoch = batches_per_epoch
        self.size = size
        self.memmap = memmap
        self.y_offset = y_offset
        
        if preprocessing_callback is None:
            self._preprocessing_callback = self._identity_preprocessing_callback
        else:
           self._preprocessing_callback = preprocessing_callback
        
        self._create_index_map()
        self._load_data()
        
        
    def __len__(self) :
        return self.batches_per_epoch
      
      
    def __getitem__(self, idx) :
        self.idx_x = np.random.choice(self._total_samples, self.batch_size)

        batch_x = list()
        batch_y = [list() for i in range(self._n_outputs)]
        for ix in self.idx_x:
            f_idx = self._file_indices[ix]
            sample_x = self._samples[ix]
            sample_y = sample_x + self.size - 1 + self.y_offset
            
            x_example = np.array(self.x_data[f_idx][sample_x : sample_x + self.size]).flatten()
            batch_x.append(x_example.reshape(( self.size,1 )) )

            for i in range(self._n_outputs):
                batch_y[i].append(np.array(
                            self.y_data[i][f_idx][sample_y])
                          )
        batch_x = np.array(batch_x)
        
        batch_x = self._preprocessing_callback(batch_x)
        for i in range(self._n_outputs):
            batch_y[i] = np.array(batch_y[i])
        
        if not self._multiple_y:
            batch_y = batch_y[0]
        
        return np.array(batch_x), batch_y


def _get_split_indices(n, split):
    n_validation= int( n * split )
    indices = np.random.permutation(n)
    validation_indices = indices[:n_validation]
    training_indices = indices[n_validation:]
    return training_indices, validation_indices
    
def split_data(x_files, y_files, y_files_2 = None, split = .2):
    '''
    Helper function to produce training and validation datasets.
    
    Positional arguments for __init__:
    x_files -- list, paths to binary files (float32), which contain input data
    y_files -- list, paths to binary files (float32), which contain output data
    '''
    
    n_files = len(x_files)
    assert n_files == len(y_files), f"Length of x_files ({n_files}) should be equal to length of y_files ({len(y_files)})!"
    
    training_indices, validation_indices = _get_split_indices(n_files, split)
    
    x_train = [x_files[i] for i in training_indices]
    x_val = [x_files[i] for i in validation_indices]
    
    y_train = [y_files[i] for i in training_indices]
    y_val = [y_files[i] for i in validation_indices]
    
    if y_files_2 is None:    
        return x_train, y_train, x_val, y_val
    
    assert n_files == len(y_files_2), f"Length of x_files ({n_files}) should be equal to length of y_files_2 ({len(y_files_2)})!"
    
    y_train_2 = [y_files_2[i] for i in training_indices]
    y_val_2 = [y_files_2[i] for i in validation_indices]
    return x_train, y_train, y_train_2, x_val, y_val, y_val_2


def _circular_difference(x,y):
    z = x-y
    return (z + np.pi) % (2*np.pi) - np.pi

def _check_circular_difference(y, y_pred):
    cdiff = _circular_difference(y, y_pred)
    plt.hist(cdiff, bins = 20, density = True)
    ax = plt.gca()
    ax.set_xticks(np.linspace(-1, 1, 5) * np.pi)
    ax.set_xticklabels(['-$\pi$', '-$\pi / 2$', '0', '$\pi / 2$', '$\pi$' ])
    ax.set_xlabel('Circular error / rad')
    ax.set_ylabel('Probablity density / rad$^{-1}$')
    mace = np.mean(np.abs(cdiff))
    print(f'MACE: {mace}')
    plt.show()

def _check_amplitude_difference(y, y_pred):
    mean = np.mean(y)
    std = np.std(y)
    y_z = (y - mean) / std
    y_pred_z = (y_pred - mean) / std
    plt.hist2d(y_z, y_pred_z, bins = 100)
    plt.xlabel('True amplitude / $z$-score')
    plt.ylabel('Predicted amplitude / $z$-score')
    r, _ = stats.pearsonr(y_z, y_pred_z)
    print(f"R_sq = {r**2}")
    plt.show()


def evaluate_phase_model(model, validation_generator, do_hilb = False, hilb_fs = None, hilb_freq = None):
    '''
    Helper function for a quick graphical evaluation of a phase model.
    
    Positional arguments:
    model -- an LFDeep phase model
    validation_generator -- a DataGenerator that produces data unseen during training
    '''
    
    x, y = validation_generator[0]
    y_pred = model(x).numpy().flatten()
    _check_circular_difference(y, y_pred)

        
    if do_hilb:
        
        y_hilb = list()
        for i in range(x.shape[0]):
            y_hilb.append(estimate_phase_hilbert(x[i,:,:].flatten(), hilb_fs, hilb_freq))
        _check_circular_difference(y, y_hilb)
    
    


def evaluate_amplitude_model(model, validation_generator):
    '''
    Helper function for a quick graphical evaluation of an amplitude model.
    
    Positional arguments:
    model -- an LFDeep phase model
    validation_generator -- a DataGenerator that produces data unseen during training
    '''
    x, y = validation_generator[0]
    y_pred = model(x).numpy().flatten()
    _check_amplitude_difference(y, y_pred)

def evaluate_joint_model(model, validation_generator, amp_idx, phase_idx):
    assert amp_idx != phase_idx
    
    x, y = validation_generator[0]
    y_pred = model(x)
    amplitude = y_pred[amp_idx].numpy().flatten()
    phase = y_pred[phase_idx].numpy().flatten()
    
    _check_circular_difference(y[phase_idx], phase)
    _check_amplitude_difference(y[amp_idx], amplitude)