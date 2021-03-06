"""
Implementation of a scene-centric texture management system.
"""

# -----------------------------------------------------------------------------
#
# Copyright (c) 1986-2018 Pixar. All rights reserved.
#
# The information in this file (the "Software") is provided for the exclusive
# use of the software licensees of Pixar ("Licensees").  Licensees have the
# right to incorporate the Software into other products for use by other
# authorized software licensees of Pixar, without fee. Except as expressly
# permitted herein, the Software may not be disclosed to third parties, copied
# or duplicated in any form, in whole or in part, without the prior written
# permission of Pixar.
#
# The copyright notices in the Software and this entire statement, including the
# above license grant, this restriction and the following disclaimer, must be
# included in all copies of the Software, in whole or in part, and all permitted
# derivative works of the Software, unless such copies or derivative works are
# solely in the form of machine-executable object code generated by a source
# language processor.
#
# PIXAR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL PIXAR BE
# LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION
# OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.  IN NO CASE WILL
# PIXAR'S TOTAL LIABILITY FOR ALL DAMAGES ARISING OUT OF OR IN CONNECTION WITH
# THE USE OR PERFORMANCE OF THIS SOFTWARE EXCEED $50.
#
# Pixar
# 1200 Park Ave
# Emeryville CA 94608
#
# -----------------------------------------------------------------------------


# TODO: handle relative image paths. Having talked with Marc B., this is
#       handled by the renderer, but we will need to implement a similar file
#       manager.
# TODO: use the FilePath class. We should move it to RMANTREE/python.

# pylint: disable=invalid-name,W0703,missing-docstring
import os
import sys
import subprocess
import json
import threading
import queue
import platform
import time
from . import (
    txm_log,
    TxManagerError,
    STATE_MISSING,
    STATE_EXISTS,
    STATE_IS_TEX,
    STATE_IN_QUEUE,
    STATE_PROCESSING,
    STATE_ERROR,
    STATE_REPROCESS,
    STATE_AS_STR,
    TXMAKE_SKIP_CONDITION,
    TEX_EXTENSIONS,
    TX_MANAGER_VER,
    IMG_EXTENSIONS,
    TEX_EXTENSIONS)
from .txfile import TxFile, _reset_rule_filecache

# posix returns -SIGKILL and windows returns 1 (error)
KILLED_SIGNALS = (1, -9)
UNBLOCK_SEMAPHORE = threading.BoundedSemaphore()


def non_ascii(string):
    """test a string for non-ASCII characters by trying to encode it to ASCII.

    Arguments:
        string {str} -- the string to be tested

    Returns:
        bool -- True is the string contains non-ASCII chars.
    """
    try:
        string.encode('ascii')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return True
    else:
        return False


def _timestamp_cmp(input_file, output_file):
    """ """
    now_time = time.time()
    input_time = os.path.getmtime(input_file)
    output_time = os.path.getmtime(output_file)

    if input_time > now_time:
        diff = input_time-now_time
        output_time = output_time+diff

    return input_time > output_time


class TxMakeOpts(object):
    """A class to hold various txmake options ex: threads"""

    def __init__(self):
        self.log = txm_log()
        self.threads = 0
        self.verbose = False
        self.dirmaps = ''

    def get_opts_as_list(self):
        args = []
        # args.append('-t:%d' % self.threads)
        if self.verbose:
            args.append('-verbose')

        if self.dirmaps:
            args.append('-dirmap %s -dirmapend' % self.dirmaps)

        return args

    def get_opts_as_dict(self):
        d = dict()
        try:
            d['threads'] = self.threads
            d['verbose'] = self.verbose
            d['dirmaps'] = self.dirmaps
        except:
            raise TxManagerError('Unable to convert TxOpts to a dictionary.')
        return d

    def set_opts_from_dict(self, d):
        for key, val in d.items():
            if val is None:
                continue
            try:
                setattr(self, key, val)
            except AttributeError:
                # warn but don't raise an error.
                self.log.error('%s is not an attribute of TxMakeOpts ! d = %r',
                               key, d)


def tx_make_process(txmanager, queue, thread_idx):
    """Function executed by threads to convert images to textures with txmake.

    Args:
    - queue (Queue.Queue): The task queue maintained by the main thread.
    """
    logger = txm_log()
    logger.debug('start')
    while not queue.empty():
        ui, txfile, txitem, args = queue.get()
        infile = args[-2]
        outfile = args[-1]

        if txfile.is_rtxplugin:
            queue.task_done()
            return

        logger.debug('%r', args)
        if not txfile.done_callback:
            logger.warning('Unexpected done callback = %r: %s',
                           txfile.done_callback, txfile.input_image)

        txfile.set_item_state(txitem, STATE_PROCESSING)
        txmanager.send_txmake_progress(txfile, txitem, txitem.state)
        start_t = time.time()
        err_msg = ''
        win_os = (platform.system() == 'Windows')
        sp_kwargs = {'stdin': subprocess.PIPE,
                     'stdout': subprocess.PIPE,
                     'stderr': subprocess.PIPE,
                     'shell': False}
        if win_os:
            sp_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            sp_kwargs['startupinfo'] = subprocess.STARTUPINFO()
            sp_kwargs['startupinfo'].dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            p = subprocess.Popen(args, **sp_kwargs)
        except Exception as err:
            logger.warning(' |_ failed to launch: %s\n    |_ args: %r',
                           err, args)
            txfile.set_item_state(txitem, STATE_ERROR)
        else:
            txmanager.subprocesses[thread_idx] = p
            lo = p.stdout.readline()
            le = p.stderr.readline()
            while lo or le:
                if lo:
                    logger.debug(lo)
                if le:
                    logger.debug(le)
                    err_msg += le
                lo = p.stdout.readline()
                le = p.stderr.readline()

        time.sleep(1.0)
        p.poll()    # get the return code

        if os.path.exists(outfile):
            stats = time.strftime(
                '%Mm:%Ss', time.localtime(time.time() - start_t))
            txfile.set_item_state(txitem, STATE_EXISTS)
            logger.info('Converted in %s : %r', stats, outfile)

            # check time stamp for future dated input files
            # if time stamp is greater than "now", we
            # give the outfile the same time stamp as the
            # input outfile
            now_time = time.time()
            infile_time = os.path.getmtime(infile)
            if infile_time > now_time:
                logger.debug('Input file, %r, is from the future!', infile)
                os.utime(outfile, (infile_time, infile_time))
        else:
            if p.returncode in KILLED_SIGNALS:
                logger.debug('KILLED: %s', args)
                txfile.set_item_state(txitem, STATE_IN_QUEUE)
            else:
                txfile.set_item_state(txitem, STATE_ERROR)
                txfile.error_msg += err_msg
                logger.error('Failed to convert: %r', infile)
                logger.error('  |__ args: %r', args)
        txitem.update_file_size()
        txfile.update_file_size()

        # update txmanager and ui
        txmanager.send_txmake_progress(txfile, txitem, txitem.state)
        txmanager.subprocesses[thread_idx] = None

        # mark task done in task queue
        queue.task_done()

    logger.debug('empty queue = done')

    unblock(txmanager)


def unblock(txmanager):
    """Check if there are any txmanager worker threads alive and set the
    queue_is_done event if this is the last one. This will unblock txmake_all()
    if the blocking flag had been set.

    Arguments:
        txmanager {TxManager} -- The main txmanager object.
    """
    UNBLOCK_SEMAPHORE.acquire()
    # avoid race condition where there are two final threads both finishing
    # at exact same time - it's possible that the second one will get here
    # before the first has finished exiting, so we'll still see two threads
    # and queue_is_done won't get set, leading to a hang where txmake_all waits
    # on queue_is_done. This sleep encourages that second to last thread to exit
    time.sleep(0.1)
    num_threads = 0
    for thread in threading.enumerate():
        if 'txmgr_worker_' in thread.name:
            num_threads += 1
    if num_threads <= 1:
        txmanager.queue_is_done.set()
    UNBLOCK_SEMAPHORE.release()


class TxManager(object):
    """A class to manage image to texture conversion in the current scene."""

    def __init__(self, **kwargs):
        """Initialize the texture manager.
        When initialized without a kwargs, it will be tagged as invalid.

        Kwargs:
        - ui:         A TxManagerUI() instance that will be called on refreshes.
                      Default to None.
        - num_workers: The number of txmake processes that should be launched.
                      Defaults to 2.
        - rmantree:   The full path to the renderman distribution. Used to locate txmake.
        - fallback_path: A fallback path if the current input texture dir is
                         writable.
        - fallback_always: Always use the fallback path to write images
        - host_prefs_func: Callback function to get preferences from the host app.
        - host_tex_done_func: Callback function to let the host app know we are
                              done converting textures.
        - host_token_resolver_func: Function the texture manager should use to resolve
                                    any host app sepcific tokens.
        """
        _reset_rule_filecache()
        self.log = txm_log()
        self.is_valid = len(kwargs) > 0
        self.ui = kwargs.get('ui', None)
        self.num_workers = kwargs.get('num_workers', 2)
        self.fallback_path = kwargs.get('fallback_path', None)
        self.fallback_always = kwargs.get('fallback_always', False)
        self.host_prefs_func = kwargs.get('host_prefs_func', None)
        self.host_tex_done_func = kwargs.get('host_tex_done_func', None)
        self.host_token_resolver_func = kwargs.get('host_token_resolver_func', None)
        self.tex_extensions = kwargs.get('texture_extensions', TEX_EXTENSIONS)
        self._id_to_txfile = dict()
        self._txfile_to_ids = dict()
        self._src_path_to_txfile = dict()
        self.txfile_list = []
        self.txmakeopts = TxMakeOpts()
        rmantree = kwargs.get('rmantree', os.environ['RMANTREE'])
        self.txmake = os.path.join(rmantree, 'bin', 'txmake')
        if platform.system() == 'Windows':
            self.txmake += '.exe'
        self.placeholder_tex = os.path.join(rmantree, 'lib', 'textures',
                                            'placeholder.tex')

        # read prefs
        self.read_host_prefs()

        # setup queue
        self.workQueue = queue.Queue()
        self.paused = False
        self.threads = []
        self.subprocesses = []
        self.queue_is_done = threading.Event()
        self.log.debug('TxManager initialized : %s', self)

    def read_host_prefs(self):
        """Execute the function provided by the host to return a dict overriding
        internal values.
        This is used to set num_workers and fallback_path.
        """
        if self.host_prefs_func:
            for key, val in self.host_prefs_func().items():
                setattr(self, key, val)
            self.log.debug('|_ num_workers = %r', self.num_workers)
            self.log.debug('|_ fallback_path = %r', self.fallback_path)

    def pickle(self):
        """Pickle the current state of TxMananger

        Returns:
            str -- JSON formatted string
        """

        state = ''

        try:
            txmanager = dict()
            txmanager['version'] = TX_MANAGER_VER
            txmanager['txmakeopts'] = self.txmakeopts.get_opts_as_dict()
            txmanager['placeholder_tex'] = self.placeholder_tex
            txmanager['num_workers'] = self.num_workers
            idsToTxFiles = dict()
            for nodeID, txfile in self._id_to_txfile.items():
                idsToTxFiles[nodeID] = txfile.as_dict()
            txmanager['_id_to_txfile'] = idsToTxFiles

            state = json.dumps(txmanager)

        except:
            raise TxManagerError('Unable to pickle TxManager')

        return state

    def unpickle(self, state):
        """Unpickle

        Arguments:
            state {str} -- string to unpickle

        """
        try:
            obj = json.loads(state)

            self.placeholder_tex = obj['placeholder_tex']
            self.num_workers = obj['num_workers']

            txmakeopts = obj['txmakeopts']
            self.txmakeopts.set_opts_from_dict(txmakeopts)

            idsToTxFiles = obj['_idsToTxFiles']

            for nodeID in list(idsToTxFiles.keys()):
                txfiledict = idsToTxFiles[nodeID]
                txfile = TxFile('', tex_ext_list=self.tex_extensions)
                txfile.set_from_dict(txfiledict)

                found = False
                for f in self.txfile_list:
                    if f == txfile:
                        found = True
                        txfile = f
                        break
                if found is False:
                    self.txfile_list.append(txfile)
                self._id_to_txfile[nodeID] = txfile
        except:
            raise TxManagerError('Unable to unpickle from: %s' % (state))

    def get_tx_make_opts(self):
        return self.txmakeopts

    def add_texture(self, nodeID, input_image,
                    nodetype='PxrTexture', category='pattern'):
        """Add texture that needs converting.
        - Optionaly applies a txmake preset to the new TxFile.
        - Checks the writability of the output directory and redirect to the
          fallback path is necessary.

        Args:
        - nodeID {str} -- ID of node this image belongs to. Typically, this is
          a plug (node.param).
        - input_image {str} -- Full path to input image

        Kwargs:
        - preset {str}:  name of a txmake preset for candidate TxFile.
        """
        if non_ascii(input_image):
            self.log.warning(
                'image path contains non-ASCII characters: ignoring %s',
                input_image)
            return
        file_ext = os.path.splitext(input_image)[-1]
        if file_ext.lower() not in IMG_EXTENSIONS + TEX_EXTENSIONS:
            if '<' not in input_image:
                # sometimes we get un-subtituted string tokens: do not warn.
                self.log.warning('Ignoring incompatible image format: %s',
                                 os.path.basename(input_image))
            return

        if nodeID in self._id_to_txfile:
            current_txfile = self._id_to_txfile[nodeID]
            if current_txfile.input_image == input_image:
                # same input image for the same id: skip
                # NOTE: will have to take fingerprint into account too,
                #       at some point !

                # even though this is a file we've already added,
                # let's take the time to double check our dirtiness
                # add_texture may have been called again, because
                # the user manually removed the .tex file on disk
                current_txfile.check_dirty(force_check=True)
                return
            else:
                if current_txfile in self._txfile_to_ids:
                    if nodeID in self._txfile_to_ids[current_txfile]:
                        # this id will use a new input image: update mapping.
                        self._txfile_to_ids[current_txfile].remove(nodeID)
                    if not self._txfile_to_ids[current_txfile]:
                        # delete reference if the txfile is not used by anyone.
                        del self._txfile_to_ids[current_txfile]
                        self.txfile_list.remove(current_txfile)
                        del self._src_path_to_txfile[current_txfile.input_image]

        txfile = TxFile(input_image, tex_ext_list=self.tex_extensions,
                        fallback_path=self.fallback_path,
                        fallback_always=self.fallback_always,
                        host_token_resolver_func=self.host_token_resolver_func)
        txfile.apply_preset(nodetype, category)

        found = False
        for f in self.txfile_list:
            if f == txfile:
                found = True
                txfile = f
                break

        if found is False:
            self._check_output_path(txfile)
            self.txfile_list.append(txfile)
            self._src_path_to_txfile[input_image] = txfile
            self.log.debug('Added %r', txfile.input_image)
        self._id_to_txfile[nodeID] = txfile

        # update the TxFile to node id mapping
        if txfile not in self._txfile_to_ids:
            self._txfile_to_ids[txfile] = [nodeID]
        elif nodeID not in self._txfile_to_ids[txfile]:
            self._txfile_to_ids[txfile].append(nodeID)

        # set the notification when a conversion is finished
        if self.host_tex_done_func:
            txfile.set_done_callback(self.host_tex_done_func, [nodeID])
        else:
            self.log.debug('host_tex_done_func = %r', self.host_tex_done_func)

        return txfile

    def get_txfile_from_id(self, node_id):
        """Get TxFile associated with this nodeID

        Arguements:
            nodeID {str} -- ID of node this image belongs to

        Returns:
            obj -- TxFile or None if nodeID is not found
        """

        if node_id in self._id_to_txfile:
            return self._id_to_txfile[node_id]
        return None

    def get_txfile_from_path(self, input_image):
        try:
            return self._src_path_to_txfile[input_image]
        except KeyError:
            return None

    def remove_texture(self, node_id):
        """remove texture from list

        Arguments:
            node_id {str} -- ID of node this image belongs to.
        """
        if node_id in self._id_to_txfile:
            txfile = self._id_to_txfile[node_id]
            del self._id_to_txfile[node_id]
            found = False
            for f in list(self._id_to_txfile.values()):
                if txfile == f:
                    found = True
                    break
            if found is False:
                self.txfile_list.remove(txfile)

    def rename_node_id(self, old_id, new_id):
        """ Rename an ID

        Arguments:
            oldID {str} -- old ID to delete
            newID {str} -- new ID to add
        """

        if old_id in self._id_to_txfile:
            txfile = self._id_to_txfile[old_id]
            del self._id_to_txfile[old_id]
            self._id_to_txfile[new_id] = txfile

    def resolve_texture_path(self, node_id, input_image):
        """ Return path to .tex file for given input_image and nodeID

        Arguments:
            nodeID {str} -- ID of node this image belongs to.
            input_image {str} -- Full path to input image

        Returns:
            str -- path to .tex file
        """

        if not node_id in self._id_to_txfile:
            self.add_texture(node_id, input_image)
        txfile = self._id_to_txfile[node_id]
        if txfile.dirty:
            return self.get_placeholder_tex()
        else:
            return txfile.get_output_texture()

    def get_placeholder_tex(self):
        """ Return placeholder tex

        Returns:
            str -- path to placeholder texture
        """
        return self.placeholder_tex

    def set_placeholder_tex(self, tex):
        self.placeholder_tex = tex

    def delete_texture_files(self):
        for txfile in self.txfile_list:
            txfile.delete_texture_files()
            self.notify_host(txfile, force=True)
        _reset_rule_filecache()
        # take this opportunity to re-read prefs
        self.read_host_prefs()

    def update_ui_list(self):
        """Tell UI to update with the current list of textures by adding a
        refresh event to the ui refresh queue."""
        if self.ui:
            if self.ui.isVisible():
                self.log.debug('refresh !')
                self.ui.update_ui(txfile_list=self.txfile_list)
            else:
                self.log.debug('updateUIList: ui is not visible')
        else:
            self.log.debug('updateUIList: ui = %r', self.ui)

    def send_txmake_progress(self, txfile, txitem, state):
        if self.ui and self.ui.isVisible():
            self.ui.ui_file_update.emit((txfile, txitem, state))
        if state == STATE_EXISTS:
            txfile.emit_done_callback()

    def _check_output_path(self, txfile):
        """
        Checks the file output path is writable and repath the outputs file(s)
        using self.fallbackPath if need be.
        We will try to create the fallback directory if it doesn't exist.
        """

        # return if input image is already a .tex
        if txfile.state == STATE_IS_TEX or txfile.is_rtxplugin:
            return

        outpath = os.path.dirname(txfile.input_image)
        # There could be a token in the outpath
        outpath = self.host_token_resolver_func(outpath)
        if self.fallback_always or not os.access(outpath, os.W_OK | os.X_OK):
            # the directory is not writable or user wants to always use the
            # fallback path.

            if self.fallback_path is None:
                self.read_host_prefs()
                path_exists = os.path.exists(self.fallback_path)
                path_writable = os.access(self.fallback_path, os.W_OK | os.X_OK)
                if path_exists and not path_writable:
                    raise TxManagerError(
                        'You MUST define a valid fallback path:'
                        ' source directory is not writable: %r' %
                        self.fallback_path)

            if not os.path.exists(self.fallback_path):
                try:
                    os.makedirs(self.fallback_path)
                except OSError as err:
                    raise TxManagerError(
                        'Could not create Fallback path: %r -> %s' %
                        (self.fallback_path, err))

            if not os.access(self.fallback_path, os.W_OK | os.X_OK):
                raise TxManagerError(
                    'Fallback path is not writable: %r' % self.fallback_path)

            # update the output tex path
            txfile.repath_outputs(self.fallback_path)

    def _start_workers(self):
        self.log.debug('Go !')
        # launch our workers
        numThreads = min(self.workQueue.qsize(), self.num_workers)
        self.log.debug('  |_ creating %d workers', numThreads)
        self.subprocesses = [None] * numThreads
        for i in range(numThreads):
            # make sure we don't create new threads if they are still alive.
            try:
                p = self.threads[i]
            except:
                pass
            else:
                if p.is_alive():
                    self.log.debug('  |_ txmgr_worker_%d is alive: skip...', i)
                    continue
                else:
                    p.join()
            # we need to create this thread now.
            self.log.debug('  |_ create txmgr_worker_%d', i)
            p = threading.Thread(target=tx_make_process,
                                 args=(self, self.workQueue, i),
                                 name='txmgr_worker_%d' % i)
            # store threads in our pool
            if i >= len(self.threads):
                self.threads.append(p)
            else:
                self.threads[i] = p
            p.start()

        self.log.debug('startWorkers done')

    def txmake_all(self, start_queue=True, blocking=False):
        """Run txmake over image list

        Keyword Arguments:
            start_queue {bool} -- Start the task queue (default: {True})
            blocking {bool} -- Block until the task queue is empty (default: {True})
        """
        self.log.debug('TxMakeAll starting...')
        if blocking:
            self.queue_is_done.clear()

        # update prefs to get the number of workers and the fallback path.
        self.read_host_prefs()
        numTasks = 0
        for txfile in self.txfile_list:
            # skip queued and processing txfiles
            if txfile.state in TXMAKE_SKIP_CONDITION:
                self.log.debug('  |_ Skipping %r, because its state is: %s',
                               txfile.input_image, STATE_AS_STR[txfile.state])
                continue
            # validate all output files
            txfile.check_dirty()
            if txfile.is_dirty():
                # one or more textures need to be generated.
                self.log.debug('  |_ %r is dirty', txfile.input_image)
                self.log.debug('     |_  %d entries in inputImageList',
                               len(txfile.tex_dict))

                # make sure the directory is writable
                self._check_output_path(txfile)

                # txmake flags
                all_flags = self.txmakeopts.get_opts_as_list() + \
                    txfile.get_params().get_params_as_list()

                for img, item in txfile.tex_dict.items():

                    # skip to the next if the texture is available.
                    if item.state not in [STATE_MISSING, STATE_REPROCESS]:
                        self.log.debug('     |_ %r is OK (%s) skip...',
                                       img, STATE_AS_STR[item.state])
                        continue

                    # skip if the source file doesn't exist
                    if not os.path.exists(item.infile):
                        txfile.set_item_state(item, STATE_ERROR)
                        self.log.debug(
                            '     |_ source file %r is missing: skip...',
                            item.infile)
                        continue

                    # create txmake command
                    argv = [self.txmake] + all_flags
                    argv.append(img)
                    argv.append(item.outfile)

                    # update state to queued
                    txfile.set_item_state(item, STATE_IN_QUEUE)

                    self.log.debug('     |_ add to work queue: %r', img)
                    self.workQueue.put([self.ui, txfile, item, argv])
                    numTasks += 1

                # add callbacks to notify nodes
                if self.host_tex_done_func:
                    node_ids = self._txfile_to_ids[txfile]
                    txfile.set_done_callback(self.host_tex_done_func, node_ids)
                else:
                    self.log.debug('self.host_tex_done_func = %r',
                                   self.host_tex_done_func)

        self.log.debug('  |_ %d tasks', numTasks)

        if start_queue and numTasks > 0:
            self.log.debug('  |_ Starting work queue processing')
            self._start_workers()

        # When the blocking flag is set, we wait until all tasks are done and
        # output progress.
        # Note: workeQueue.qsize() may already be empty at this point,
        # because the work has been popped off the queue, but isn't actually
        # done yet, so we still need to wait in this loop until queue_is_done
        # has been set.
        if blocking and numTasks:
            self.log.info('Processing %d txmake tasks using %d workers...',
                          numTasks, self.num_workers)
            ntasks = float(numTasks)
            t_start = time.time()
            while not self.queue_is_done.is_set():
                self.queue_is_done.wait(2.0)
                # approximation: there is at least one thread still alive, so we
                # add one to show that at least one worker is still active.
                num_done = min(self.workQueue.qsize() + 1, numTasks)
                percent = 100.0 - (float(num_done) / ntasks * 100.0)
                print(('R90000%5d%%' % percent), file=sys.stderr)
            self.log.info('%s texture conversions tasks done in %s !', numTasks,
                          time.strftime('%Mm %Ss',
                                        time.localtime(time.time() - t_start)))

    def notify_host(self, txfile, force=False):
        if not self.host_tex_done_func:
            return

        try:
            node_ids = self._txfile_to_ids[txfile]
        except KeyError:
            self.log.warning('%r not in %s:\n%s\ntxm = %r', txfile,
                             list(self._txfile_to_ids.keys()), txfile, self)
        else:
            txfile.set_done_callback(self.host_tex_done_func, node_ids)
            txfile.emit_done_callback(force=force)

    def flush_queue(self):
        while self.workQueue.qsize():
            self.workQueue.get()
            self.workQueue.task_done()
        # kill workers
        for process in self.subprocesses:
            if process is None:
                continue
            try:
                process.kill()
            except OSError as err:
                # sometimes the process has finished before we get to kill it.
                self.log.info('Failed to kill %s: %s (it may happen)',
                              process.pid, err)
            else:
                time.sleep(0.25)
                self.log.info('Killed txmake with pid %s', process.pid)
        time.sleep(0.25)

    def all_textures_available(self):
        return self.workQueue.qsize() == 0

    def reset(self):
        self.flush_queue()
        self.txfile_list = []
        self._id_to_txfile = dict()
        self._txfile_to_ids = dict()
        self._src_path_to_txfile = dict()
        self.paused = False
        _reset_rule_filecache()

    def file_size(self):
        f_size = 0
        for txfile in self.txfile_list:
            f_size += txfile.file_size
        return f_size

    def __del__(self):
        self.log.debug('TxManager deleted : %s', self)
        try:
            self.flush_queue()
        except:
            pass
