# Where the experiment's files live on this machine, for the bash scripts, which source this file. Python scripts
# use power_paths.py, which has the same defaults and describes each location. Set any of these in the environment
# to override; they're exported so the Python each script starts agrees.
POWER_V0_HOME=${POWER_V0_HOME:-$HOME/power-v0}
POWER_V0_DATA=${POWER_V0_DATA:-$POWER_V0_HOME/data}
POWER_V0_CT=${POWER_V0_CT:-$POWER_V0_HOME/src/control-tower}
export POWER_V0_HOME POWER_V0_DATA POWER_V0_CT
