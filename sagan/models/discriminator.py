import numpy as np
import tensorflow as tf
from tensorflow.keras import Model, Input, layers
from layers import SNConv2D, SNDense, AttentionLayer


def Block(inputs, output_channels):
    x = SNConv2D(output_channels, 4, 2, padding='same')(inputs)
    x = layers.LeakyReLU(alpha=0.1)(x)
    return x

def get_discriminator(config):
    df_dim = config['df_dim']
    img = Input(shape=(config['img_size'], config['img_size'], 3), batch_size=config['batch_size'], name='image')
    condition_label = Input(shape=(), batch_size=config['batch_size'], dtype=tf.int32, name='condition_label')
    x = img
    
    # to handle different size of images.
    power = np.log2(config['img_size'] / 4).astype('int') # 64->4; 128->5
    for p in range(power):
        x = Block(x, df_dim * 2 ** p)
        if config['use_attention'] and int(x.shape[1]) in config['attn_dim_G']:
            x = AttentionLayer()(x)

    if config['use_label']:
        x = tf.reduce_sum(x, axis=[1,2])
        outputs = layers.Dense(1)(x)
        # embedding = layers.Embedding(config['num_classes'], df_dim * 2 ** (power-1))
        # label_feature = SpectralNormalization(embedding)(condition_label)
        label_feature = layers.Embedding(config['num_classes'], df_dim * 2 ** (power-1))(condition_label)
        outputs += tf.reduce_sum(x * label_feature, axis=1, keepdims=True)
        return Model(inputs=[img, condition_label], outputs=outputs)
    else:
        outputs = layers.Conv2D(1, 4, 1, padding='same')(x)
        return Model(inputs=[img, condition_label], outputs=outputs)

def Optimized_Block(inputs, output_channels):
    x = SNConv2D(output_channels, 3, 1, padding='same')(inputs)
    x = layers.LeakyReLU(alpha=0.1)(x)

    x = SNConv2D(output_channels, 3, 2, padding='same')(x) # downsample

    x_ = SNConv2D(output_channels, 3, 2, padding='same')(inputs)

    return layers.add([x_, x])

# Don't mind resnet for now.
def Res_Block(inputs, output_channels, downsample=True):
    stride = 2 if downsample else 1

    x = layers.LeakyReLU(alpha=0.1)(inputs)
    x = SNConv2D(output_channels, 3, 1, padding='same')(x)
    
    x = layers.LeakyReLU(alpha=0.1)(x)
    x = SNConv2D(output_channels, 3, stride, padding='same')(x)

    x_ = layers.LeakyReLU(alpha=0.1)(inputs)
    x_ = SNConv2D(output_channels, 3, stride, padding='same')(x_)

    return layers.add([x_, x])

def get_res_discriminator(config):
    df_dim = config['df_dim']
    img = Input(shape=(config['img_size'], config['img_size'], 3), name='image')
    power = np.log2(config['img_size'] / 4).astype('int')
    condition_label = Input(shape=(), dtype=tf.int32, name='condition_label')

    x = Optimized_Block(img, df_dim * 1) # 64x64
    for p in range(1, power):
        x = Res_Block(x, df_dim * 2 ** p)  # 32x32
        if config['use_attention'] and int(x.shape[1]) in config['attn_dim_G']:
            x = AttentionLayer()(x)
    
    x = Res_Block(x, df_dim * 2 ** power, downsample=False) # 4x4

    
    if config['use_label']:
        x = layers.ReLU()(x)
        x = tf.reduce_sum(x, axis=[1,2])
        outputs = SNDense(1)(x)
        label_feature = layers.Embedding(config['num_classes'], df_dim * 16)(condition_label)
        
        outputs += tf.reduce_sum(x * label_feature, axis=1, keepdims=True)
        return Model(inputs=[img, condition_label], outputs=outputs)
    else:
        outputs = layers.SNConv2D(1, 4, 1, padding='same')(x)
        return Model(inputs=[img, condition_label], outputs=outputs)