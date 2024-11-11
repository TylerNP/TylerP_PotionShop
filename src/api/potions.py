from fastapi import APIRouter, Depends
from src.api import auth
import random

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/potions",
    tags=["potion"],
    dependencies=[Depends(auth.get_api_key)],
)


def create_random_potion(increment : int, type : int, price : int) -> dict[str, any]:
    """
    Generate a random potion using an increment to determine the difference between them
    Type 1 Gives a uneven distribution roughly 50/25/12/6
    Type 2 Gives a more uniform distribution
    """
    if (increment > 100):
        return ValueError
    random.seed(version=2)
    num_types = 4
    potion_type = [0]*num_types
    total = 100
    if type == 1: 
        index = random.randrange(0,num_types)
        for index in range(num_types-1):
            potion_type[index] = random.randrange(0,total+1,increment)
            total = total - potion_type[index]  
            index = (index+1)%4
        potion_type[index] = total
    elif (type == 2):
        if total%increment != 0:
            potion_type[random.randrange(0,num_types)] = total%increment
        for _ in range(total//increment):
            potion_type[random.randrange(0,num_types)] += increment
    else:
        return NotImplemented
    strings = generate_name_sku(potion_type)
    return {
                "sku":strings["sku"],
                "name":strings["name"],
                "price":price,
                "red":potion_type[0],
                "green":potion_type[1],
                "blue":potion_type[2],
                "dark":potion_type[3]
    }

def generate_name_sku(potion_type : list[int]) -> dict[str, str]:
    """
    Generate a simply name and sku with red, green, blue, and dark
    """
    ml_types = ["r", "g", "b", "d"]
    num_types = 4
    sku = ""
    name = ""
    for index in range(num_types):
        sku += ml_types[index] + str(potion_type[index])
        if (index != num_types-1):
            sku += '_'
        if potion_type[index] != 0:
            name += ml_types[index] + str(potion_type[index])
            if (index == num_types-1):
                break
            name += '_'
    if name[-1] == "_":
        name = name[0:len(name)-1]
    return {
                "sku":sku,
                "name":name
    }

def vary_potion(potion : dict[str, any], step : int, degree : int) -> dict[str, any]:
    """
    Generate a variant of the given potion adjusting the "main" color with 
    changes determined by step and degree
    """
    if degree > 3 or degree < 1:
        return ValueError
    potion_type = potion["potion_type"]
    main = potion_type.index(max(potion_type))
    max_ml = 100
    if potion_type[main] >= step:
        num_types = 4
        change = step // degree
        if step%degree != 0:
            index = main
            while index == main:
                index = random.randrange(0, num_types)
            potion_type[index] += step%degree
        for _ in range(degree):
            index = main
            while index == main:
                index = random.randrange(0, num_types)
            potion_type[index] += change
        potion_type[main] -= step
        strings = generate_name_sku(potion_type)
        return {
                    "sku":strings["sku"],
                    "name":strings["name"],
                    "price":potion["price"],
                    "red":potion_type[0],
                    "green":potion_type[1],
                    "blue":potion_type[2],
                    "dark":potion_type[3]
        }
    elif step//degree < max_ml:
        return create_random_potion(step//degree, 2, potion["price"])
    else:
        return ValueError

def insert_new_potion(potion : dict[str, any]) -> bool:
    print(potion)
    sql_to_execute = """
        SELECT 1 FROM potions WHERE red = :red AND green = :green AND blue = :blue AND dark = :dark
    """
    insert = False
    with db.engine.begin() as connection:
        try: 
            connection.execute(sqlalchemy.text(sql_to_execute), potion).scalar_one()
        except sqlalchemy.exc.NoResultFound:
            sql_to_execute = """
                INSERT INTO potions (price, sku, name, red, green, blue, dark) 
                VALUES (:price, :sku, :name, :red, :green, :blue, :dark)
            """
            connection.execute(sqlalchemy.text(sql_to_execute), potion)
            sql_to_execute = """
                INSERT INTO new_potion (sku, tick_created) VALUES (:sku, (SELECT MAX(id) FROM time))
            """
            connection.execute(sqlalchemy.text(sql_to_execute), potion)
            insert = True
        print(f"Added New Potion {potion}: {insert}")
    return insert