import os
import unittest
import tempfile
import shutil

import pyirk.refactor_tools as rt



from .settings import (
    TEST_BASE_URI,
    TEST_DATA_DIR1,
    HousekeeperMixin,
    TEST_DATA_DIR_OCSE,
    TEST_DATA_PATH3 as ocse_subset_agents_path,
)


# noinspection PyPep8Naming
class Test_01_Script(HousekeeperMixin, unittest.TestCase):
    def test_rt_a01__change_entity_label(self):

        tmp_mod_fpath = make_temp_copy_of_file(ocse_subset_agents_path)

        # change I9942["Stanford University"] to I9942["Renamed Stanford University"]
        rt.change_entity_label(key="I9942", new_label="Renamed Stanford University", fpath=tmp_mod_fpath)

        manually_checking_difference = False
        if manually_checking_difference:
            tmp_mod_fpath0 = make_temp_copy_of_file(ocse_subset_agents_path)
            os.system(f"kdiff3 {tmp_mod_fpath0} {tmp_mod_fpath}")


    def test_rt_a02__change_entity_label_from_cli(self):

        tmp_mod_fpath = make_temp_copy_of_file(ocse_subset_agents_path)

        cmd = f'pyirk --refactor-entity-label I9942 "Renamed Stanford University" {tmp_mod_fpath}'
        os.system(cmd)


        manually_checking_difference = False
        if manually_checking_difference:
            tmp_mod_fpath0 = make_temp_copy_of_file(ocse_subset_agents_path)
            os.system(f"kdiff3 {tmp_mod_fpath0} {tmp_mod_fpath}")
#
# Auxiliary functions:
#

def make_temp_copy_of_file(fpath):
    """
    Creates a temporary file with the content of the file specified by `fpath`
    """
    # Create a temporary file and copy the content from the source file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".py")
    try:
        # Close the file descriptor since shutil.copy2 will handle the file operations
        import os
        os.close(temp_fd)
        # Copy the file content and metadata
        shutil.copy2(fpath, temp_path)
        return temp_path
    except Exception:
        # Clean up the temporary file if something goes wrong
        try:
            os.unlink(temp_path)
        except:
            pass
        raise
