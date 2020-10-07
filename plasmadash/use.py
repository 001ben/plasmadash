import pyarrow as pa
from pyarrow import plasma

def get_plasma():
    return plasma.connect('/tmp/plasma')

def pd_put(df):
    get_plasma().put(pa.Table.from_pandas(df))
