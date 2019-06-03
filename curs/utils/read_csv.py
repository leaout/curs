import pandas as pd
import os
import datetime
import time

# names open high low ...;  csv_path
def ReadFromCsv(names, csv_path, skip_rows = 0,sep='\t'):
    df = pd.read_csv(csv_path, sep=sep, names=names, header=None, encoding="gb2312",skiprows=skip_rows)
    # data = np.array(df)
    #df.columns = [''.join(icol.split()) for icol in df.columns.values.tolist()]
    return df

def GetFileName(full_name):
    return os.path.splitext(os.path.basename(full_name))[0]

def WalkDir(rootdir):
    l_file = []
    list = os.listdir(rootdir)
    for i in range(0, len(list)):
        path = os.path.join(rootdir, list[i])
        if os.path.isfile(path):
            l_file.append(path)
    return l_file

def WalkSubDir(rootdir):
    l_dirs = []
    list = os.listdir(rootdir)
    for i in range(0, len(list)):
        path = os.path.join(rootdir, list[i])
        if os.path.isdir(path):
            l_dirs.append(path)
    return l_dirs

def timestamp_to_unix(time_stamp):
    '''
    :param time_stamp 2005-01-04 09:31:00:
    :return:
    '''
    a = datetime.datetime.strptime(str(time_stamp), "%Y-%m-%d %H:%M:%S").timetuple()
    b = time.mktime(a)
    return int(b)

def main():
    list_dirs = WalkSubDir("D:/JoinQuant-Desktop-Py3/USERDATA/.joinquant-py3/bundle/stock1d/00")
    print(list_dirs)
    for dir in list_dirs:
        print(os.path.basename(dir))
    pass



if __name__ == '__main__':
    main()
