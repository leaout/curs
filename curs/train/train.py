import numpy as np 
import pandas as pd
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM,Dropout
from tensorflow.keras.callbacks import EarlyStopping
# from sklearn.preprocessing import MinMaxScaler

print(os.getcwd())
# 读取历史数据
df = pd.read_csv('curs/train/600519.txt', header=None)
custom_headers = ['datetime',  'open','high', 'low',  'close',  'volume','amt'  ]
df.columns = custom_headers
# 选择要操作的股票代码
# stock_code = 'AAPL'
# df = df[df['code'] == stock_code].reset_index(drop=True)

# 构造训练集和测试集
train_size = int(len(df) * 0.8)
df_train = df[:train_size]
df_test = df[train_size:]

# 选择输入和输出
x_train = df_train[['open', 'high', 'low', 'close', 'volume']].values[:-1]
y_train = df_train['close'].shift(-1).values[:-1] 
x_test = df_test[['open', 'high', 'low', 'close', 'volume']].values[:-1]
y_test = df_test['close'].shift(-1).values[:-1] 

# # 数据归一化
# scaler = MinMaxScaler()
# x_train = scaler.fit_transform(x_train)
# x_test = scaler.transform(x_test)
# 重新构造输入数据为三维张量
timesteps = 1  # 可以根据需要调整时间步长
x_train = x_train.reshape((x_train.shape[0] , timesteps, x_train.shape[1]))
x_test = x_test.reshape((x_test.shape[0] , timesteps, x_test.shape[1]))
# 构建LSTM模型
print(y_train)
model = Sequential()
print(x_train.shape[1:])
model.add(LSTM(100, return_sequences=True, input_shape=(timesteps,x_train.shape[2])))
model.add(Dropout(0.2))
model.add(LSTM(70, return_sequences=True))
model.add(Dropout(0.2))
model.add(Dense(1))
model.compile(loss='mse', optimizer='adam')

# 训练模型
model.fit(
    x_train, y_train, 
    validation_data=(x_test, y_test), 
    epochs=30, 
    batch_size=2,
    callbacks=[EarlyStopping(patience=3)],
    verbose=1
)

# 评估模型
loss = model.evaluate(x_test, y_test, verbose=0) 
print(f'Test loss: {loss}')

# 预测并展示结果
predicted = model.predict(x_test)
print(predicted)
df_test = df_test[:-1] 

# df_test.loc[:, 'Predictions'] = predicted
# df_test['Predictions'] = df_test['Predictions'].astype(float)
# reslt = df_test[['datetime','close', 'Predictions']].tail(20)
print(df_test.tail(20))
