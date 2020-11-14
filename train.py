from utils import *
import model
import time
import matplotlib.pyplot as plt
from config import *
from tensorflow.python.ops import variables
from tensorflow.python.framework import ops

class Train(object):
    def __init__(self, trial, step, size, scale_list, meta_batch_size, meta_lr, meta_iter, task_batch_size, task_lr, task_iter, data_generator, checkpoint_dir, conf):
        self.trial = trial
        self.step=step
        self.HEIGHT=size[0]
        self.WIDTH=size[1]
        self.CHANNEL=size[2]
        self.scale_list=scale_list

        self.META_BATCH_SIZE = meta_batch_size
        self.META_LR = meta_lr
        self.META_ITER = meta_iter

        self.TASK_BATCH_SIZE = task_batch_size
        self.TASK_LR = task_lr
        self.TASK_ITER = task_iter

        self.data_generator=data_generator
        self.checkpoint_dir=checkpoint_dir
        self.conf=conf

        self.inputa = tf.placeholder(dtype=tf.float32, shape=[self.META_BATCH_SIZE, self.TASK_BATCH_SIZE, self.HEIGHT, self.WIDTH, self.CHANNEL])
        self.inputb = tf.placeholder(dtype=tf.float32, shape=[self.META_BATCH_SIZE, self.TASK_BATCH_SIZE, self.HEIGHT, self.WIDTH, self.CHANNEL])

        self.labela = tf.placeholder(dtype=tf.float32, shape=[self.META_BATCH_SIZE, self.TASK_BATCH_SIZE, self.HEIGHT, self.WIDTH, self.CHANNEL])
        self.labelb = tf.placeholder(dtype=tf.float32, shape=[self.META_BATCH_SIZE, self.TASK_BATCH_SIZE, self.HEIGHT, self.WIDTH, self.CHANNEL])

        self.PARAM=model.Weights(scope='MODEL')
        self.weights=self.PARAM.weights

        self.MODEL = model.MODEL(name='MODEL')

    def construct_model(self):
        #self.stop_grad=tf.Variable(True, name='stop_grad', trainable=False)

        def task_metalearn(inp):
            task_init_weight = list(self.weights.values())
            inputa, inputb, labela, labelb = inp
            loss_func = tf.losses.absolute_difference

            task_outputbs, task_lossesb = [], []

            self.MODEL.forward(inputa, self.weights)
            task_outputa = self.MODEL.output

            weights = self.MODEL.param
            task_lossa = loss_func(labela, task_outputa)

            grads = tf.gradients(task_lossa, list(weights.values()))

            gradients = dict(zip(weights.keys(), grads))
            fast_weights = dict(
                zip(weights.keys(), [weights[key] - self.TASK_LR * gradients[key] for key in weights.keys()]))

            self.MODEL.forward(inputb, fast_weights)
            output = self.MODEL.output

            task_outputbs.append(output)
            task_lossesb.append(loss_func(labelb, output))

            for j in range(self.TASK_ITER - 1):
                self.MODEL.forward(inputa, fast_weights)
                output_s = self.MODEL.output

                loss = loss_func(labela, output_s)
                grads = tf.gradients(loss, list(fast_weights.values()))

                gradients = dict(zip(fast_weights.keys(), grads))
                fast_weights = dict(zip(fast_weights.keys(),
                                        [fast_weights[key] - self.TASK_LR * gradients[key] for key in
                                         fast_weights.keys()]))

                self.MODEL.forward(inputb, fast_weights)
                output = self.MODEL.output

                task_outputbs.append(output)
                task_lossesb.append(loss_func(labelb, output))

            task_final_weight = list(fast_weights.values())
            task_weight_diff = [v1 - v2 for v1, v2 in zip(task_init_weight, task_final_weight)]
            task_weight_diff = [v/0.01 for v in task_weight_diff]
            task_output = [task_outputa, task_outputbs, task_lossa, task_lossesb, task_weight_diff]

            return task_output

        out_dtype = [tf.float32, [tf.float32] * self.TASK_ITER, tf.float32, [tf.float32] * self.TASK_ITER, [tf.float32, tf.float32, tf.float32, tf.float32, tf.float32, tf.float32, tf.float32,tf.float32,tf.float32,tf.float32,tf.float32,tf.float32,tf.float32,tf.float32,tf.float32,tf.float32]]
        result = tf.map_fn(task_metalearn, elems=(self.inputa, self.inputb, self.labela, self.labelb), dtype=out_dtype,
                           parallel_iterations=self.META_BATCH_SIZE, name='task_metalearn')

        self.outputas, self.outputbs, self.lossesa, self.lossesb, self.task_weight_diff = result

    def __call__(self):
        self.print_lossa = []
        self.print_lossa_mean = []
        self.print_lossb = []
        self.print_lossb_mean = []
        PRINT_ITER=100
        SAVE_ITER=1000

        print('[*] Setting Train Configuration')

        self.construct_model()

        self.global_step=tf.Variable(self.step, name='global_step', trainable=False)

        self.total_loss1 = tf.reduce_sum(self.lossesa) / tf.to_float(self.META_BATCH_SIZE)

        self.total_losses2 =  [tf.reduce_sum(self.lossesb[j]) / tf.to_float(self.META_BATCH_SIZE) for j in range(self.TASK_ITER)]

        self.var_list = variables.trainable_variables() + ops.get_collection(ops.GraphKeys.TRAINABLE_RESOURCE_VARIABLES)
        #self.var_list = variables.trainable_variables()

        self.subGrad_var = [tf.Variable(v, name='subtractGrad', trainable=False) for v in self.var_list]

        self._placeholder = [tf.placeholder(v.dtype.base_dtype, shape=v.get_shape()) for v in self.var_list]
        assigns = [tf.assign(v, p, name='assign') for v, p in zip(self.subGrad_var, self._placeholder)]
        self._assign_op = tf.group(*assigns)

        self.Gradprt = tf.Print(self.subGrad_var[4], [self.subGrad_var[4]], name='Gradprt')
        self.check = tf.Print(self.var_list[2], [self.var_list[2]], name='check')
        '''Optimizers'''

        self.pretrain_op = tf.train.AdamOptimizer(self.META_LR).minimize(self.total_loss1)
        self.opt = tf.train.AdamOptimizer(self.META_LR, name='MetaAdam')

        self.gvs = list(zip(self.subGrad_var, self.var_list))
        self.metatrain_op= self.opt.apply_gradients(self.gvs, name='applyGrad')

        self.squee = [tf.squeeze(v) for v in self.task_weight_diff]
        '''Summary'''
        self.summary_op = tf.summary.merge([tf.summary.scalar('Train Pre_update loss', self.total_loss1)]+
                                           [tf.summary.scalar('Train Post_update loss, step %d' % (j+1), self.total_losses2[j]) for j in range(self.TASK_ITER)]+
                                           [tf.summary.image('1.Input_query', tf.clip_by_value(self.inputb[0], 0., 1.),
                                                             max_outputs=4),
                                            tf.summary.image('2.output_query', tf.clip_by_value(self.outputbs[self.TASK_ITER-1][0], 0., 1.),
                                                             max_outputs=4),
                                            tf.summary.image('3.GT', self.labelb[0], max_outputs=4)
                                            ])


        self.saver=tf.train.Saver(max_to_keep=100000)
        pretrain_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='MODEL')
        self.loader = tf.train.Saver(var_list=pretrain_vars)
        self.init=tf.global_variables_initializer()

        count_param(scope='MODEL')

        with tf.Session(config=self.conf) as sess:
            sess.run(self.init)
            if IS_TRANSFER:
                self.loader.restore(sess, TRANS_MODEL)
                print('==================== PRETRAINED MODEL Loading Succeeded ====================')

            could_load, model_step = load(self.saver, sess, self.checkpoint_dir, folder='Model%d' % self.trial)
            if could_load:
                print('Iteration:', self.step)
                print('==================== Loading Succeeded ===================================')
                assert self.step == model_step, 'The latest step and the input step do not match.'
            else:
                print('==================== No model to load ======================================')

            writer = tf.summary.FileWriter('../logs', sess.graph)

            print('[*] Training Starts')

            step = self.step

            t2 = time.time()

            while True:
                try:
                    inputa, labela, inputb, labelb = self.data_generator.make_data_tensor(sess, self.scale_list, noise_std=0.0)

                    '''feed & fetch'''
                    feed_dict = {self.inputa: inputa, self.inputb: inputb, self.labela: labela, self.labelb: labelb}

                    if step == 0:
                        sess.run(self.metatrain_op, feed_dict=feed_dict)
                    else:
                        task_weight_diff = sess.run(self.squee, feed_dict = feed_dict)
                        sess.run(self._assign_op, feed_dict=dict(zip(self._placeholder, task_weight_diff)))
                        sess.run(self.Gradprt)
                        sess.run(self.metatrain_op, feed_dict=feed_dict)

                    lossa_, lossb_, summary = sess.run([self.total_loss1, self.total_losses2[-1], self.summary_op], feed_dict=feed_dict)

                    self.print_lossa.append(lossa_)
                    self.print_lossb.append(lossb_)

                    print('Iteration:', step, '(Pre, Post) Loss:', lossa_, lossb_)

                    step += 1

                    if step % PRINT_ITER == 0:
                        t1 = t2
                        t2 = time.time()

                        self.print_lossa_mean.append(np.mean(self.print_lossa))
                        self.print_lossb_mean.append(np.mean(self.print_lossb))

                        lossa_, lossb_, summary = sess.run([self.total_loss1, self.total_losses2[-1], self.summary_op], feed_dict=feed_dict)

                        print('Iteration:', step, '(Pre, Post) Loss:', lossa_, lossb_, 'Time: %.2f' % (t2 - t1))

                        writer.add_summary(summary, step)
                        writer.flush()

                    if step % SAVE_ITER == 0:
                        print_time()
                        save(self.saver, sess, self.checkpoint_dir, self.trial, step)

                    if step == self.META_ITER:
                        listforprint = np.linspace(0, step, len(self.print_lossa_mean))
                        plt.plot(listforprint, self.print_lossa_mean)
                        plt.plot(listforprint, self.print_lossb_mean)
                        plt.title("Model training loss accuarcy")
                        plt.xlabel("Iteration")
                        plt.ylabel("Accuracy")
                        plt.legend(["Pre task training Loss", "Post task training Loss"])
                        plt.show()
                        print('Done Training')
                        print_time()
                        break


                except KeyboardInterrupt:
                    print('***********KEY BOARD INTERRUPT *************')
                    print('Iteration:', step)
                    print_time()
                    save(self.saver, sess, self.checkpoint_dir, self.trial, step)
                    break

    def get_loss_weights(self):
        loss_weights = tf.ones(shape=[self.TASK_ITER]) * (1.0/self.TASK_ITER)
        decay_rate = 1.0 / self.TASK_ITER / (10000 / 3)
        min_value= 0.03 / self.TASK_ITER

        loss_weights_pre = tf.maximum(loss_weights[:-1] - (tf.multiply(tf.to_float(self.global_step), decay_rate)), min_value)

        loss_weight_cur= tf.minimum(loss_weights[-1] + (tf.multiply(tf.to_float(self.global_step),(self.TASK_ITER- 1) * decay_rate)), 1.0 - ((self.TASK_ITER - 1) * min_value))
        loss_weights = tf.concat([[loss_weights_pre], [[loss_weight_cur]]], axis=1)
        return loss_weights
