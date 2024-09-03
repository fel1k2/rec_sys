import pandas as pd
from implicit.nearest_neighbours import TFIDFRecommender 
from rectools import Columns
from rectools.dataset import Dataset
from rectools.models import ImplicitItemKNNWrapperModel
from tkinter import messagebox, ttk
import tkinter as tk
import hashlib
import os
import threading
import time


ratings = pd.read_csv(
    "ratings.csv", 
    sep=":",
    engine="python",  
    header=None,
    names=[Columns.User, Columns.Item, Columns.Weight, Columns.Datetime],
)
dataset = Dataset.construct(ratings)
model = ImplicitItemKNNWrapperModel(TFIDFRecommender(K=5))
model.fit(dataset)
print(model.recommend(users=ratings[Columns.User].unique(), 
            dataset=dataset,
            k=5,
            filter_viewed=True,
        ))

cold_correcting=0


def update_model():
    global ratings, dataset, model
    ratings = pd.read_csv(
        "ratings.csv", 
        sep=":",
        engine="python",  
        header=None,
        names=[Columns.User, Columns.Item, Columns.Weight, Columns.Datetime],
    )
    dataset = Dataset.construct(ratings)
    model.fit(dataset)


user_ratings_map = {user: True for user in ratings[Columns.User].astype(str).unique()}


root = tk.Tk()
root.title("GameRecsDemo")
root.geometry("300x150")
root.resizable(width=False, height=False)


sign_in_button = tk.Button(root, width=17, text="Войти", command=lambda: sign_in(root))
sign_in_button.pack(pady=30)


sign_up_button = tk.Button(root, width=17, text="Зарегистрироватсья", command=lambda: sign_up(root))
sign_up_button.pack(pady=0)


def generate_salt():
    return os.urandom(16)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)


def save_to_file(login, salt, hashed_password, filename='users.txt'):
    global ratings
    idx = ratings[Columns.User].max() + 1
    with open(filename, 'a') as file:
        file.write(f"{login}:{salt.hex()}:{hashed_password.hex()}:{idx}\n")


def register_user(login, password):
    salt = generate_salt()  
    hashed_password = hash_password(password, salt)  
    save_to_file(login, salt, hashed_password)


def check_password(login, password, root, login_label, login_entry, password_label, password_entry, back_button, sign_in_button_accept, filename='users.txt'):
    is_entered = False
    with open(filename, 'r') as file:
        for line in file:
            saved_login, saved_salt, saved_hash, idx = line.strip().split(':')
            if saved_login == login:
                salt = bytes.fromhex(saved_salt)
                hashed_password = hash_password(password, salt)
                if hashed_password.hex() == saved_hash:
                    is_entered = True
                    messagebox.showinfo("Успех!", "Вы успешно вошли в аккаунт!")
                    found = user_ratings_map.get(idx, False)
                    main_form(root, login_label, login_entry, password_label, password_entry, back_button, sign_in_button_accept, found, idx)
                    break

    if not is_entered:
        messagebox.showwarning("Ошибка.", "Неправильные логин и/или пароль")


def get_top_rated_items(ratings, top_n=10, start=0):
    top_items = ratings.groupby(Columns.Item)[Columns.Weight].mean()
    top_items = top_items.sort_values(ascending=False)
    top_items = top_items.iloc[start:start + top_n]
    return top_items.index.tolist()


def show_top_rated_items(root, idx, start=0):
    root.geometry("300x780")
    top_items = get_top_rated_items(ratings, start=start)
    label = tk.Label(root, text="Пожалуйста, оцените следующие игры:")
    label.pack(pady=10)
    widgets = [label]
    entries = []
    rate=[0, 1, 2, 3, 4, 5]
    for item in top_items:
        item_label = tk.Label(root, text=f"Игра {item}:")
        item_label.pack(pady=5)
        combobox = ttk.Combobox(values=rate, state="readonly")
        combobox.pack(pady=5)
        widgets.append(item_label)
        widgets.append(combobox)
        entries.append((item, combobox))
    
    submit_button = tk.Button(root, text="Сохранить оценки", command=lambda: data_from_new_user(root, entries, idx, widgets))
    submit_button.pack(pady=10)
    widgets.append(submit_button)


def data_from_new_user(root, entries, idx, widgets):
    global model
    ratings_to_save=[]
    for item, combobox in entries:
        if combobox.get() != '':
            ratings_to_save.append((item, combobox))
    save_ratings(ratings_to_save, idx)
    update_model()
    for widget in widgets:
        widget.forget()
    show_recommendations(root, idx)


def save_ratings(entries, idx):
    for item, entry in entries:
        if entry.get() != '':
            try:
                rating = float(entry.get())
                timestamp=int(time.time())
                new_data = pd.DataFrame({
                    'UserID': [idx],
                    'ItemID': [item],
                    'Rating': [rating],
                    'Timestamp': [timestamp]
                })
                new_data.to_csv('ratings.csv', mode='a', header=False, index=False, sep=":")
            except ValueError as e:
                pass
            

def still_cold(root, user_id, widgets, start):
    messagebox.showinfo("Нужно бпольше информации.","Для более точных рекомендаций оцените ещё несколько игр.")
    if len(widgets) > 0:
        for widget in widgets:
            widget.forget()
    show_top_rated_items(root, user_id, start=start)


def show_recommendations(root, user_id):
    global model, dataset, cold_correcting
    widgets=[]
    cold_correcting += 10
    user_id = int(user_id)
    root.geometry("300x460")
    user_ratings = ratings[ratings[Columns.User] == user_id]
    if user_ratings.empty:
        messagebox.showwarning("Ошибка", "У пользователя нет оценок.")
        print(f"Оценок для пользователя {user_id} не найдено.")
        show_top_rated_items(root, user_id, start=cold_correcting)
        return
    print(f"Найдено {len(user_ratings)} оценок для пользователя {user_id}.")
    try:
        print(user_id)
        recos1 = model.recommend(
            users=[int(user_id)], 
            dataset=dataset,
            k=5,
            filter_viewed=True,
        )

        if len(recos1) < 5:
            still_cold(root, user_id, widgets, start=cold_correcting)
            return

        rec_label = tk.Label(root, text="Рекомендованные игры для вас:")
        rec_label.pack(pady=10)
        
        widgets.append(rec_label)
        rec_entries = []
        n=1
        rate=[0, 1, 2, 3, 4, 5]
        for item_id in recos1[Columns.Item]:
            rec_label = tk.Label(root, text=f"Рекомендация {n}: Игра {item_id}")
            rec_label.pack(pady=5)
            combobox = ttk.Combobox(values=rate, state="readonly")
            combobox.pack(pady=5)
            rec_entries.append((item_id, combobox))
            widgets.append(rec_label)
            widgets.append(combobox)
            n += 1
        
        submit_button = tk.Button(root, text="Сохранить оценки и продолжить", command=lambda: save_and_get_next_recommendations(root, user_id, rec_entries, widgets))
        submit_button.pack(pady=10)
        widgets.append(submit_button)
    
    except ValueError as e:
        messagebox.showwarning("Ошибка", f"Ошибка при получении рекомендаций: {e}")
        print(f"Ошибка при получении рекомендаций для пользователя {user_id}: {e}")

def save_and_get_next_recommendations(root, user_id, rec_entries, widgets):
    for widget in widgets:
        widget.forget()
    save_ratings(rec_entries, user_id)
    update_model()
    show_recommendations(root, user_id)


def main_form(root, login_label, login_entry, password_label, password_entry, back_button, sign_in_button_accept, found, idx):
    login_label.forget()
    login_entry.forget()
    password_label.forget()
    password_entry.forget()
    back_button.forget()
    sign_in_button_accept.forget()
    if found:
        show_recommendations(root, int(idx))
    else:
        show_top_rated_items(root, int(idx))


def sign_in(root):
    sign_in_button.forget()
    sign_up_button.forget()
    
    root.geometry("300x300")
    
    login_label = tk.Label(root, text="Введите логин:")
    login_label.pack(pady=10)
    login_entry = tk.Entry(root)  
    login_entry.pack(pady=10)

    password_label = tk.Label(root, text="Введите пароль:")
    password_label.pack(pady=10)
    password_entry = tk.Entry(root)  
    password_entry.pack(pady=10)
    back_button = tk.Button(root, text="Назад", command = lambda: back(root, sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button))

    sign_in_button_accept = tk.Button(root, text="Войти", command = lambda:check_password(login_entry.get(), password_entry.get(), root, login_label, login_entry, password_label, password_entry, back_button, sign_in_button_accept))
    sign_in_button_accept.pack(pady=10)
    
    back_button.pack(pady=10)


def sign_up(root):
    sign_in_button.forget()
    sign_up_button.forget()
    
    root.geometry("300x400")
    
    login_label = tk.Label(root, text="Введите логин:")
    login_label.pack(pady=10)
    login_entry = tk.Entry(root)  
    login_entry.pack(pady=10)

    password_label = tk.Label(root, text="Введите пароль:")
    password_label.pack(pady=10)
    password_entry = tk.Entry(root)  
    password_entry.pack(pady=10)

    password_confirm_label = tk.Label(root, text="Подтвердите пароль:")
    password_confirm_label.pack(pady=10)
    password_confirm_entry = tk.Entry(root)  
    password_confirm_entry.pack(pady=10)

    sign_in_button_accept = tk.Button(root, text="Зарегистрироваться", command=lambda: register(root, login_entry.get(), password_entry.get(), password_confirm_entry.get(), sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button, password_confirm_label=password_confirm_label, password_confirm_entry=password_confirm_entry))
    sign_in_button_accept.pack(pady=10)
    
    back_button = tk.Button(root, text="Назад", command = lambda: back(root, sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button, password_confirm_label=password_confirm_label, password_confirm_entry=password_confirm_entry))
    back_button.pack(pady=10)


def register(root, login, password, repeated_password, sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button, password_confirm_label, password_confirm_entry):
    if password == repeated_password and password != '' and login!='':
        register_user(login, password)
        back(root, sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button, password_confirm_label=password_confirm_label, password_confirm_entry=password_confirm_entry)
        messagebox.showinfo("Успех!", "Вы успешно зарегистрировались!")
    elif password == repeated_password and (password == '' or login==''):
        messagebox.showwarning("Ошибка.", "Заполните все поля.")
    elif password != repeated_password:
        messagebox.showwarning("Ошибка.", "Пароли не совпадают.")


def back(root, sign_in_button_accept, password_entry, password_label, login_label, login_entry, back_button, password_confirm_label = 0, password_confirm_entry=0):
    root.geometry("300x150")
    login_label.forget()
    login_entry.forget()
    sign_in_button_accept.forget()
    password_entry.forget()
    password_label.forget()
    back_button.forget()
    if password_confirm_label:password_confirm_label.forget()
    if password_confirm_entry:password_confirm_entry.forget()
    sign_in_button.pack(pady=30)
    sign_up_button.pack(pady=0)
root.mainloop()
