import os
import unittest
from backup_rsync.backup import Backup, Startpoint, Endpoint, Server, Logging, Path_f
import sys
import tempfile
import os.path as path
from datetime import datetime


class TestCommandFormat(unittest.TestCase):
    def test_minimal(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination')
        )
        cmd = br._create_rsync_command()

        # check non-optional part
        self.assertEqual(cmd.pop(0), 'rsync')
        self.assertEqual(cmd.pop(), '/destination/')
        self.assertEqual(cmd.pop(), '/source/')
        # standard expected options
        try:
            cmd.remove('--verbose')
            cmd.remove('--progress')
            cmd.remove('--update')
            cmd.remove('--recursive')
            cmd.remove('--compress')
            cmd.remove('--checksum')
            cmd.remove('--links')
            cmd.remove('--times')
            cmd.remove('--delete')
            cmd.remove('--delete-excluded')
            cmd.remove('--one-file-system')
        except ValueError:
            self.fail('myFunc() raised ExceptionType unexpectedly!')

        # check optional are not active
        self.assertEqual(cmd, [])

    def test_partial(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', partial='/partial')
        )
        cmd = br._create_rsync_command()
        self.assertIn('--partial', cmd)
        self.assertIn('--partial-dir=/partial/', cmd)

    def test_exclude_single(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            exclude='single'
        )
        cmd = br._create_rsync_command()
        self.assertIn('--exclude=single', cmd)

    def test_exclude_quote(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            exclude='single space'
        )
        cmd = br._create_rsync_command()
        self.assertIn('--exclude=single space', cmd)

    def test_exclude_list(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            exclude=['one', 'two', 'three']
        )
        cmd = br._create_rsync_command()
        self.assertIn('--exclude=one', cmd)
        self.assertIn('--exclude=two', cmd)
        self.assertIn('--exclude=three', cmd)

    def test_history(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', history='/history'),
        )
        cmd = br._create_rsync_command()
        self.assertIn('--backup', cmd)
        self.assertIn('--backup-dir=/history/', cmd)

    def test_progress(self):
        br = Backup(
            source=Startpoint(Path_f('/source')),
            destination=Endpoint('/destination'),
            logging=Logging(actions='/actions',
                            progress='/progress',
                            errors='/errors'),
        )
        cmd = br._create_rsync_command()
        self.assertIn('--log-file=/actions', cmd)

    def test_logfile_space(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            logging=Logging(actions='/actions with space')
        )
        cmd = br._create_rsync_command()
        self.assertIn('--log-file=/actions with space', cmd)

    def test_rsync_local_path(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            rsync_local_path='/sbin/rsync'
        )
        cmd = br._create_rsync_command()
        self.assertEqual(cmd.pop(0), '/sbin/rsync')

    def test_missing_server(self):
        with self.assertRaises(ValueError):
            br = Backup(
                source=Startpoint('/source', remote=True),
                destination=Endpoint('/destination')
            )

    def test_2_remotes(self):
        with self.assertRaises(ValueError):
            br = Backup(
                source=Startpoint('/source', remote=True),
                destination=Endpoint('/destination', remote=True),
                server=Server('url')
            )

    def test_remote_source(self):
        br = Backup(
            source=Startpoint('/source', remote=True),
            destination=Endpoint('/destination'),
            server=Server('url')
        )
        cmd = br._create_rsync_command()
        self.assertEqual(cmd.pop(), '/destination/')
        self.assertEqual(cmd.pop(), 'url:/source/')

    def test_remote_destination(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', remote=True),
            server=Server('url')
        )
        cmd = br._create_rsync_command()
        self.assertEqual(cmd.pop(), 'url:/destination/')
        self.assertEqual(cmd.pop(), '/source/')

    def test_remote_timeout(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', remote=True),
            server=Server('url', timeout=60)
        )
        cmd = br._create_rsync_command()
        self.assertIn('--timeout=60', cmd)

    def test_remote_port(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', remote=True),
            server=Server('url', port=60)
        )
        cmd = br._create_rsync_command()
        self.assertIn('--rsh=ssh -p 60', cmd)

    def test_remote_keyfile(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', remote=True),
            server=Server('url', keyfile='/keyfile')
        )
        cmd = br._create_rsync_command()
        self.assertIn('--rsh=ssh -i "/keyfile"', cmd)

    def test_remote_rsyncpath(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination', remote=True),
            server=Server('url', rsyncpath='/rsyncpath')
        )
        cmd = br._create_rsync_command()
        self.assertIn('--rsh=ssh --rsync-path="/rsyncpath"', cmd)

    def test_relative_path_f(self):
        root_path = '/root/path'
        br = Backup(
            source=Startpoint(
                path=Path_f('source', cwd=root_path)),
            destination=Endpoint(
                path=Path_f('destination', cwd=root_path),
                partial=Path_f('partial', cwd=root_path),
                history=Path_f('history', cwd=root_path)),
            logging=Logging(
                actions=Path_f('actions', cwd=root_path)),
            server=Server(
                url='url',
                keyfile=Path_f('keyfile', cwd=root_path)),
        )
        cmd = br._create_rsync_command()
        self.assertEqual(cmd.pop(), '/root/path/destination/')
        self.assertEqual(cmd.pop(), '/root/path/source/')
        self.assertIn('--partial-dir=/root/path/partial/', cmd)
        self.assertIn('--backup-dir=/root/path/history/', cmd)
        self.assertIn('--log-file=/root/path/actions', cmd)
        self.assertIn('--rsh=ssh -i "/root/path/keyfile"', cmd)

    def test_absolute_path_f(self):
        root_path = '/root/path'
        br = Backup(
            source=Startpoint(
                path=Path_f('/source', cwd=root_path)),
            destination=Endpoint(
                path=Path_f('/destination', cwd=root_path),
                partial=Path_f('/partial', cwd=root_path),
                history=Path_f('/history', cwd=root_path)),
            logging=Logging(
                actions=Path_f('/actions', cwd=root_path)),
            server=Server(
                url='url',
                keyfile=Path_f('/keyfile', cwd=root_path)),
        )
        cmd = br._create_rsync_command()
        self.assertEqual(cmd.pop(), '/destination/')
        self.assertEqual(cmd.pop(), '/source/')
        self.assertIn('--partial-dir=/partial/', cmd)
        self.assertIn('--backup-dir=/history/', cmd)
        self.assertIn('--log-file=/actions', cmd)
        self.assertIn('--rsh=ssh -i "/keyfile"', cmd)

    def test_dryrun(self):
        br = Backup(
            source=Startpoint('/source'),
            destination=Endpoint('/destination'),
            dryrun=True
        )
        cmd = br._create_rsync_command()
        self.assertIn('--dry-run', cmd)
        self.assertIn('--itemize-changes', cmd)


class TestProcess(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self._tmp_src_dir = tempfile.TemporaryDirectory()
        self._tmp_dst_dir = tempfile.TemporaryDirectory()
        self._tmp_log_dir = tempfile.TemporaryDirectory()
        self.tmp_src_dirpath = self._tmp_src_dir.name
        self.tmp_dst_dirpath = self._tmp_dst_dir.name
        self.tmp_log_dirpath = self._tmp_log_dir.name
        # self.tmp_src_dirpath = '/tmp/a/'
        # self.tmp_dst_dirpath = '/tmp/b/'
        # self.tmp_log_dirpath = '/tmp/l/'
        self.sample_filename = 'sample.txt'
        self.tmp_src_filepath = path.join(self.tmp_src_dirpath, self.sample_filename)
        self.tmp_dst_filepath = path.join(self.tmp_src_dirpath, self.sample_filename)
        self.tmp_actions_filepath = path.join(self.tmp_log_dirpath, 'actions.txt')
        self.tmp_errors_filepath = path.join(self.tmp_log_dirpath, 'errors.txt')
        self.tmp_progress_filepath = path.join(self.tmp_log_dirpath, 'progress.txt')

        with open(self.tmp_src_filepath, 'w') as sample_file:
            sample_file.write(datetime.now().isoformat())

    def tearDown(self):
        # Remove the directory after the test
        self._tmp_src_dir.cleanup()
        self._tmp_dst_dir.cleanup()
        self._tmp_log_dir.cleanup()

    @unittest.skipIf(sys.platform.startswith('win'), 'no rsync on windows')
    def test_call_log(self):
        br = Backup(
            source=Startpoint(self.tmp_src_dirpath),
            destination=Endpoint(self.tmp_dst_dirpath),
            logging=Logging(
                actions=self.tmp_actions_filepath,
                errors=self.tmp_errors_filepath,
                progress=self.tmp_progress_filepath
            )
        )
        br.save()

        # check backup is conforming
        self.assertTrue(path.exists(self.tmp_dst_filepath))
        with open(self.tmp_src_filepath) as expect,  open(self.tmp_dst_filepath) as result:
            self.assertListEqual(list(expect), list(result))
        # check log files
        self.assertTrue(path.exists(self.tmp_actions_filepath))
        self.assertFalse(path.exists(self.tmp_errors_filepath))
        self.assertFalse(path.exists(self.tmp_progress_filepath))
        # with open(self.tmp_actions_filepath) as log:
        #     print(f'================ actions ({self.tmp_actions_filepath}) '.ljust(80, '='))
        #     print(log.read())
        #     print('================ /actions '.ljust(80, '='))

    @unittest.skipIf(sys.platform.startswith('win'), 'no rsync on windows')
    def test_call_none_log(self):
        br = Backup(
            source=Startpoint(self.tmp_src_dirpath),
            destination=Endpoint(self.tmp_dst_dirpath),
            logging=Logging(
                actions=None,
                errors=None,
                progress=None
            )
        )
        br.save()


if __name__ == '__main__':
    unittest.main()
