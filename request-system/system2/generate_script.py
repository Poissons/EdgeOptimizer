import pandas as pd
import random

file_path = './request/batch_task_mini.csv'
test_file_path = './request/batch_task_mini_test.csv'
data = pd.read_csv(file_path)
random.seed(0)
data['1.1'] = data['1.1'].apply(lambda x: random.randint(1, 20))
data['86207'] = data['86207'].apply(lambda x: int((x - 86207)/2))
data['86210'] = data['86207']
data['86210'] = data['86210']+data['1.1']+2
print(data)
data.to_csv(test_file_path, index=False)
