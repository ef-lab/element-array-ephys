import numpy as np
import sys
import os
import pathlib
import datajoint as dj
from element_array_ephys import probe, ephys, ephys_report
import element_interface

dj.config['database.host'] = 'database.eflab.org:3306'
dj.config['database.username'] = 'maria'
dj.config['database.password'] = 'Spike@Thr200'

experiment_dir = '/mnt/lab/data01/OpenEphys'
db_prefix = 'lab_npx_'
dj.config["enable_python_native_blobs"] = True
dj.config['custom'] = {'database_prefix': db_prefix,'ephys_root_data_dir': experiment_dir}

dj.conn()

schemata = {'experiment_db'   : 'lab_experiments',
            'stimulus_db'     : 'lab_stimuli',
            'behavior_db'     : 'lab_behavior',
            'recording_db'    : 'lab_recordings',
            'mice_db'         : 'lab_mice' }

# # create a virtual module for every database schema that you are going to use
for schema, value in schemata.items():
    globals()[schema] = dj.create_virtual_module(schema, value, create_tables=True, create_schema=True)

if "custom" not in dj.config:
    dj.config["custom"] = {}

# overwrite dj.config['custom'] values with environment variables if available

dj.config["custom"]["database_prefix"] = os.getenv(
    "DATABASE_PREFIX", dj.config["custom"].get("database_prefix", "")
)

dj.config["custom"]["ephys_root_data_dir"] = os.getenv(
    "EPHYS_ROOT_DATA_DIR", dj.config["custom"].get("ephys_root_data_dir", "")
)

def replace_directory(a_directory):
    """
    Temporary Solution, use common.Paths.getLocal instead
    """
    # Define the mapping
    old_prefix1 = 'X:/OpenEphys\\'
    new_prefix1 = '/mnt/lab/data/OpenEphys/'

    old_prefix2 = 'W:/OpenEphys\\'
    new_prefix2 = '/mnt/lab/data01/OpenEphys/'

    old_prefix3 = 'W:/OpenEphys'
    new_prefix3 = '/mnt/lab/data01/OpenEphys/'

    # Replace the prefix
    if a_directory.startswith(old_prefix1):
        return a_directory.replace(old_prefix1, new_prefix1)
    elif a_directory.startswith(old_prefix2):
        return a_directory.replace(old_prefix2, new_prefix2)
    elif a_directory.startswith(old_prefix3):
        return a_directory.replace(old_prefix3, new_prefix3)
    else:
        print('Something is wrong with the OpenEphys path')
        

# Declare functions for retrieving data
def get_ephys_root_data_dir():
    """Retrieve ephys root data directory."""
    ephys_root_dirs = dj.config.get("custom", {}).get("ephys_root_data_dir", None)
    if not ephys_root_dirs:
        return None
    elif isinstance(ephys_root_dirs, (str, pathlib.Path)):
        return [ephys_root_dirs]
    elif isinstance(ephys_root_dirs, list):
        return ephys_root_dirs
    else:
        raise TypeError("`ephys_root_data_dir` must be a string, pathlib, or list")


def get_session_directory(session_key: dict) -> str:
    """Retrieve the session directory with Neuropixels for the given session.

    Args:
        session_key (dict): A dictionary mapping subject to an entry in the subject table, and session_datetime corresponding to a session in the database.

    Returns:
        A string for the path to the session directory.
    """
    rep_dir = replace_directory((recording_db.Recording & session_key).fetch1("target_path"))
    print(rep_dir)
    if not rep_dir:
        raise ValueError(f"No path found for key: {session_key}")
    print(rep_dir)
    
    session_dir = element_interface.utils.find_full_path(
        get_ephys_root_data_dir(),
        rep_dir
    )
    return session_dir/'Record Node 101/experiment1/recording1'  


def get_processed_root_data_dir() -> str:
    """Retrieve the root directory for all processed data.

    Returns:
        A string for the full path to the root directory for processed data.
    """
    return get_ephys_root_data_dir()[0]


@experiment_db.schema
class SkullReference(dj.Lookup):
    definition = """
    skull_reference   : varchar(60)
    """
    contents = zip(["Bregma", "Lambda"])


Experimenter = experiment_db.Session
Session      = experiment_db.Session
Subject      = experiment_db.Session
Recording    = recording_db.Recording


probe.activate(db_prefix + "probe")
ephys.activate(db_prefix + "ephys", linking_module=__name__)
ephys_report.activate(db_prefix + "ephys_report")

probe.create_neuropixels_probe_types()


__all__ = [""]