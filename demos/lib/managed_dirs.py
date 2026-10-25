"""Print the current import and analysis directories (relative to the managed project) of group 'main':
python managed_dirs.py MANAGED_PROJECT  ->  "<import_dir> <analysis_dir>" """
import sys
from rnplens import state
h = state.Project(sys.argv[1]).head()
a = h["analyses"]["main"]
print(a["import_dir"], a["dir"])
