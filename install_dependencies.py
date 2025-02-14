
def InstallDependencies():
    try:
        import epo_ops
    except ImportError:
        import os
        os.system('pip install python-epo-ops-client')
        import epo_ops

    try:
        from epo.tipdata.ops import OPSClient, models, exceptions
    except ImportError:
        import os
        os.system('pip install epo-tipdata-ops')
        from epo.tipdata.ops import OPSClient, models, exceptions

    try:
        import pandas_read_xml as pdx
    except ImportError:
        import os
        os.system('pip install pandas_read_xml')
        import pandas_read_xml as pdx

    try:
        import openpyxl
    except ImportError:
        os.system('pip install openpyxl')
        import openpyxl        


    try:
        import ipywidgets as widgets
    except ImportError:
        os.system('pip install ipywidgets')
        import ipywidgets as widgets

    import pandas as pd
    pd.set_option('display.max_columns', None)
    pd.set_option('display.expand_frame_repr', False)
