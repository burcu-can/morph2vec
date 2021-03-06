from __future__ import print_function
from __future__ import unicode_literals

import codecs
import sys

import keras.backend as K
import numpy
from gensim.models import KeyedVectors
from keras import regularizers
from keras.engine import Model
from keras.layers import Input
from keras.layers.core import Dense, Lambda, Reshape, Masking
from keras.layers.embeddings import Embedding
from keras.layers.merge import concatenate
from keras.layers.recurrent import LSTM
from keras.layers.wrappers import TimeDistributed, Bidirectional
from keras.preprocessing import sequence

number_of_segmentation = 10

number_of_unique_morpheme = 8

print('===================================  Prepare data...  ==============================================')
print('')

word2sgmt = {}
word2segmentations = {}
seq = []
morphs = []

f = codecs.open('sample.txt', encoding='utf-8')
for line in f:
    line = line.rstrip('\n')
    word, sgmnts = line.split(':')
    sgmt = sgmnts.split('+')
    word2segmentations[word] = list(s for s in sgmt)
    sgmt = list(s.split('-') for s in sgmt)
    word2sgmt[word] = sgmt
    seq.extend(sgmt)

timesteps_max_len = 0

for sgmt in seq:
    if len(sgmt) > timesteps_max_len: timesteps_max_len = len(sgmt)
    for morph in sgmt:
        morphs.append(morph)

print('number of words: ', len(word2sgmt))

morph_indices = dict((c, i + 1) for i, c in enumerate(set(morphs)))
morph_indices['###'] = 0

indices_morph = dict((i+1, c) for i, c in enumerate(set(morphs)))
indices_morph[0] = '###'

print('')
print('===================================  Load Input and Output...  ===============================================')
print('')

x_train = numpy.load("x_train.npy")

print('')
print('===================================  Build model...  ===============================================')
print('')

morph_seg = []
for i in range(number_of_segmentation):
    morph_seg.append(Input(shape=(None,), dtype='int32'))

morph_embedding = Embedding(input_dim=number_of_unique_morpheme, output_dim=50, mask_zero=True, name="embeddding")

embed_seg = []
for i in range(number_of_segmentation):
    embed_seg.append(morph_embedding(morph_seg[i]))

biLSTM = Bidirectional(LSTM(200, dropout=0.2, recurrent_dropout=0.2, return_sequences=False), merge_mode='concat')

encoded_seg = []
for i in range(number_of_segmentation):
    encoded_seg.append(biLSTM(embed_seg[i]))

concat_vector = concatenate(encoded_seg, axis=-1)
merge_vector = Reshape((number_of_segmentation, 400))(concat_vector)

masked_vector = Masking()(merge_vector)

seq_output = TimeDistributed(Dense(200))(masked_vector)

attention_1 = TimeDistributed(Dense(units=200, activation='tanh', use_bias=False))(seq_output)

attention_2 = TimeDistributed(Dense(units=1,
                                    activity_regularizer=regularizers.l1(0.01),
                                    use_bias=False))(attention_1)


def attn_merge(inputs, mask):
    vectors = inputs[0]
    logits = inputs[1]
    # Flatten the logits and take a softmax
    logits = K.squeeze(logits, axis=2)
    pre_softmax = K.switch(mask[0], logits, -numpy.inf)
    weights = K.expand_dims(K.softmax(pre_softmax))
    return K.sum(vectors * weights, axis=1)


def attn_merge_shape(input_shapes):
    return (input_shapes[0][0], input_shapes[0][2])


attn = Lambda(attn_merge, output_shape=attn_merge_shape)
attn.supports_masking = True
attn.compute_mask = lambda inputs, mask: None
content_flat = attn([seq_output, attention_2])

model = Model(inputs=morph_seg, outputs=content_flat)

model.load_weights("weights.h5")


def attn_weight(inputs, mask):
    vectors = inputs[0]
    logits = inputs[1]
    # Flatten the logits and take a softmax
    logits = K.squeeze(logits, axis=2)
    pre_softmax = K.switch(mask[0], logits, -numpy.inf)
    weights = K.expand_dims(K.softmax(pre_softmax))
    return weights


def attn_weight_shape(input_shapes):
    return (input_shapes[0][0], input_shapes[0][2])


attn_w = Lambda(attn_weight, output_shape=attn_weight_shape)
attn_w.supports_masking = True
attn_w.compute_mask = lambda inputs, mask: None
content_w = attn_w([attention_1, attention_2])

s_model = Model(inputs=model.input, outputs=content_w)
model.summary()

q = s_model.predict([x_train[i] for i in range(len(x_train))])
#print(q)

max = -numpy.inf
for i in range(len(q)):
    max_index = numpy.argmax(q[i])
    #print(x_train[max_index][i])
    s = ""
    for k in x_train[max_index][i]:
        if k != 0:
            s = s + indices_morph[k] + " "
    print(s)
