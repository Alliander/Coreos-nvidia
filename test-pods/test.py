import tensorflow as tf
import argparse

parser = argparse.ArgumentParser(description='My program description')
parser.add_argument('--input1-path', type=str,
                    help='Path of the local file containing the Input 1 data.')  # Paths should be passed in, not hardcoded
parser.add_argument('--output1-path', type=str,
                    help='Path of the local file where the Output 1 data should be written.')  # Paths should be passed in, not hardcoded
# parser.add_argument('--param1', type=int, default=100, help='Parameter 1.')
args = parser.parse_args()


def kubeflow_tensor_gpu(input: str):
    with tf.device('/gpu:0'):
        a = tf.constant(str, shape=[2, 3], name='a')
        b = tf.constant(str, shape=[3, 2], name='b')
        c = tf.matmul(a, b)

    with tf.Session() as sess:
        with open(args.output1_path, 'w') as out_file:
            out_file.write(sess.run(c))


kubeflow_tensor_gpu(args.input1_path)
