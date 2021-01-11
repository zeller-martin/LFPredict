Note: While the package is functional, it is still work in progress and at an experimental stage.

# LFDeep

LFDeep contains utilities to predict the instantaneous amplitude and phase of a signal in a specific frequency band under causal conditions, using the unfiltered broadband signal as an input. The repository contains code for end-to-end training of neural networks in Keras, given training data where amplitude or phase are extracted from the broadband input using digital acausal filtering.

The projected and intended use lies in real-time prediction on local field potentials (LFP), which serve as a signature of oscillatory brain activity. Experimentalists can thus incorporate LFDeep models within their experimental toolchain, to deliver stimuli in a manner that is conditional on the instantaneous amplitude or phase of a band-limited oscillation within the broadband LFP signal.

# Prerequisities

LFDeep needs Tensorflow 2, numpy, scipy and matplotlib. Having a GPU Tensorflow installation will speed up training and inference, but for the comparatively shallow networks it is not strictly necessary. Examples may have additional dependencies.

# Installation

to be written ...

# Quickstart

Proceed as follows:

1. Choose a dataset, and decide whether to predict amplitude or phase.
1. Create training data, by subsampling to e.g. 1 kHz, and saving raw binaries in float32 of the broadbrand signal and extracted amplitudes. An example script is found at examples/create_training_data/script.py.
1. Train and evaluate the network. Example workflows are given in examples/training/.
1. Incorporate prediction into your specific setup for closed-loop stimulation. An exemplary full description of a hard- and software system with LFDeep at its core is given in examples/implementation.
