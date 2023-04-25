import numpy as np 
import pandas as pd
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM
from tensorflow.keras.callbacks import EarlyStopping

# 读取历史数据
df = pd.read_csv('stock_data.csv')

# 选择要操作的股票代码
stock_code = 'AAPL'
df = df[df['code'] == stock_code].reset_index(drop=True)

# 构造训练集和测试集
train_size = int(len(df) * 0.8)
df_train = df[:train_size]
df_test = df[train_size:]

# 选择输入和输出
x_train = df_train[['open', 'high', 'low', 'close', 'volume']].values
y_train = df_train['close'].shift(-1).values
x_test = df_test[['open', 'high', 'low', 'close', 'volume']].values
y_test = df_test['close'].shift(-1).values

# 构建LSTM模型
model = Sequential()
model.add(LSTM(50, return_sequences=True, input_shape=(x_train.shape[1:])))
model.add(LSTM(50))
model.add(Dense(1))
model.compile(loss='mse', optimizer='adam')

# 训练模型
model.fit(
    x_train, y_train, 
    validation_data=(x_test, y_test), 
    epochs=50, 
    batch_size=32,
    callbacks=[EarlyStopping(patience=3)],
    verbose=1
)

# 评估模型
loss = model.evaluate(x_test, y_test, verbose=0) 
print(f'Test loss: {loss}')

# 预测并展示结果
predicted = model.predict(x_test)
df_test.loc[:, 'Predictions'] = predicted
df_test[['close', 'Predictions']].tail()