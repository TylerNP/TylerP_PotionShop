from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import random

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ 
    Update database values for ml and potions
    """
    ml_used = [0]*4
    ml_red = []
    ml_green = []
    ml_blue = []
    ml_dark = []
    quantities = []
    for potion in potions_delivered:
        quantities.append(potion.quantity)
        ml_red.append(potion.potion_type[0])
        ml_green.append(potion.potion_type[1])
        ml_blue.append(potion.potion_type[2])
        ml_dark.append(potion.potion_type[3])
        ml_used[0] += potion.potion_type[0]*potion.quantity
        ml_used[1] += potion.potion_type[1]*potion.quantity
        ml_used[2] += potion.potion_type[2]*potion.quantity
        ml_used[3] += potion.potion_type[3]*potion.quantity
    with db.engine.begin() as connection:
        values = {
                    "quantities":quantities, 
                    "ml_red":ml_red, 
                    "ml_green":ml_green, 
                    "ml_blue":ml_blue, 
                    "ml_dark":ml_dark,
                    "order_id":order_id
                }
        sql_to_execute = """
                            UPDATE potions
                            SET quantity = quantity + p.pot_quantity
                            FROM (SELECT 
                            UNNEST(:quantities) AS pot_quantity,
                            UNNEST(:ml_red) AS pot_red,
                            UNNEST(:ml_green) AS pot_green,
                            UNNEST(:ml_blue) AS pot_blue,
                            UNNEST(:ml_dark) AS pot_dark)
                            AS p
                            WHERE red = p.pot_red
                            AND green = p.pot_green
                            AND blue = p.pot_blue
                            And dark = p.pot_dark
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            SELECT 'Brewed: ' || p.pot_quantity || ' ' || potions.sku || ', ' as details
                            FROM potions, (
                                SELECT UNNEST(:quantities) AS pot_quantity,
                                UNNEST(:ml_red) AS pot_red,
                                UNNEST(:ml_green) AS pot_green,
                                UNNEST(:ml_blue) AS pot_blue,
                                UNNEST(:ml_dark) AS pot_dark)
                                AS p
                            WHERE red = p.pot_red
                            AND green = p.pot_green
                            AND blue = p.pot_blue
                            And dark = p.pot_dark
                        """
        texts = connection.execute(sqlalchemy.text(sql_to_execute), values)
        concat_text = ""
        for text in texts:
            concat_text = concat_text + text.details
        values["text"] = concat_text
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id)
                            VALUES (:text, (SELECT time.id FROM time ORDER BY time.id DESC LIMIT 1))
                            RETURNING id
                        """
        transaction_id = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
        values["transaction_id"] = transaction_id
        sql_to_execute = """
                            INSERT INTO potion_ledgers (sku, quantity, order_id, transaction_id)
                            SELECT p.sku, q.pot_quantity, :order_id, :transaction_id 
                            FROM potions AS p, 
                                (SELECT UNNEST(:ml_red) AS pot_red, 
                                UNNEST(:ml_green) AS pot_green, 
                                UNNEST(:ml_blue) AS pot_blue, 
                                UNNEST(:ml_dark) AS pot_dark, 
                                UNNEST(:quantities) AS pot_quantity) AS q
                            WHERE q.pot_red = p.red 
                            AND q.pot_green = p.green
                            AND q.pot_blue = p.blue
                            AND q.pot_dark = p.dark
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET num_red_ml = num_red_ml - :red,
                            num_green_ml = num_green_ml - :green,
                            num_blue_ml = num_blue_ml - :blue,
                            num_dark_ml = num_dark_ml - :dark,
                            num_potions = (SELECT SUM(quantity) FROM potions)
                        """
        values = {
                    "red":ml_used[0], 
                    "green":ml_used[1], 
                    "blue":ml_used[2], 
                    "dark":ml_used[3],
                    "order_id":order_id,
                    "transaction_id":transaction_id
                }
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO ml_ledgers (num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, order_id, transaction_id)
                            VALUES (-1*:red, -1*:green, -1*:blue, -1*:dark, :order_id, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
    print("used %d mls" % (ml_used[0]+ml_used[1]+ml_used[2]+ml_used[3]))

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Determine what potions to brew from remaining ml 
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    ml_available = [0]*4
    ml_max = [0]*4
    unique_potions = []
    potion_brew_amount = []
    potion_storage_left = 0
    with db.engine.begin() as connection: 
        sql_to_execute = """
                            SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, 
                            potion_capacity*50/(SELECT COUNT(1) FROM potions WHERE brew = TRUE) AS threshold,
                            potion_capacity*50-(SELECT SUM(quantity) FROM potions) AS remaining_storage 
                            FROM global_inventory
                        """
        results = connection.execute(sqlalchemy.text(sql_to_execute))
        potion_threshold = 0
        potion_storage_left = 0
        for result in results:
            ml_available[0] = result.num_red_ml
            ml_available[1] = result.num_green_ml
            ml_available[2] = result.num_blue_ml
            ml_available[3] = result.num_dark_ml
            potion_threshold = result.threshold
            potion_storage_left = result.remaining_storage

        sql_to_execute = """
                            SELECT red, green, blue, dark, quantity 
                            FROM potions 
                            WHERE quantity < :quantity 
                            AND red <= :red_amt 
                            AND green <= :green_amt 
                            AND blue <= :blue_amt 
                            AND dark <= :dark_amt 
                            and brew = TRUE
                            ORDER BY quantity ASC, price DESC
                        """
        values = [
                    {
                        "quantity":potion_threshold, 
                        "red_amt":ml_available[0], 
                        "green_amt":ml_available[1], 
                        "blue_amt":ml_available[2], 
                        "dark_amt":ml_available[3]
                    }
                ]
        potions_brewable = connection.execute(sqlalchemy.text(sql_to_execute), values)
        for potion in potions_brewable:
            unique_potions.append([potion.red, potion.green, potion.blue, potion.dark])
            desired_potion_brew_count = potion_threshold-potion.quantity
            potion_brew_amount.append(desired_potion_brew_count)
            ml_max[0] += potion.red*desired_potion_brew_count
            ml_max[1] += potion.green*desired_potion_brew_count
            ml_max[2] += potion.blue*desired_potion_brew_count
            ml_max[3] += potion.dark*desired_potion_brew_count

    return bottle_plan_calculation(potion_brew_amount, ml_available, ml_max, unique_potions, potion_storage_left)

def bottle_plan_calculation(
                                potion_brew_amount : list[int], 
                                ml_available : list[int], 
                                ml_needed : list[int], 
                                unique_potions : list[list[int]], 
                                potion_storage_left : int
                            ) -> list[dict[str, any]]:
    """
    Determines how much of each potion to brew
    """
    if not potion_brew_amount:
        return []
    plan = []
    potion_index = 0
    potion_count = len(unique_potions)
    potion_unavailable = [0]*potion_count
    unique_potion_counts = [0]*potion_count
    ml_types = ["red", "green", "blue", "dark"]
    min = potion_brew_amount[-1]
    potion_brew_ratio = [ round(quantity/min) for quantity in potion_brew_amount]
    brew_ratio_copy = potion_brew_ratio.copy()
    ml_usable = [ ml_available[index] if ml_available[index] < ml_needed[index] else ml_needed[index] for index in range(len(ml_needed))]
    ml_used = ml_usable.copy()
    count = 0
    loop_count = 0
    while potion_storage_left > 0 and not all (potion_unavailable):
        count += 1
        if not any(brew_ratio_copy):
            brew_ratio_copy = potion_brew_ratio.copy()
        if brew_ratio_copy[potion_index] == 0 or potion_unavailable[potion_index] == 1:
            potion_index = (potion_index+1)%potion_count
            loop_count = loop_count + 1
            if loop_count > potion_count:
                print("opps")
                break
            continue
        loop_count = 0
        brewed = True
        ml_leftover = [0]*4
        for index in range(len(ml_usable)):
            ml_leftover[index]= ml_usable[index] - unique_potions[potion_index][index]
            if ml_leftover[index] < 0:
                brewed = False
                break
        if not brewed:
            potion_unavailable[potion_index] = 1
            potion_brew_ratio[potion_index] = 0
            brew_ratio_copy[potion_index] = 0
            continue
        potion_storage_left = potion_storage_left - 1
        ml_usable = [ml for ml in ml_leftover]
        unique_potion_counts[potion_index] += 1
        brew_ratio_copy[potion_index] -= 1
        if potion_brew_amount[potion_index] == unique_potion_counts[potion_index]:
            potion_unavailable[potion_index] = 1
        potion_index = (potion_index+1)%len(unique_potions)

    print(f"Looped: {count} Times") 
    for i in range(len(unique_potions)):
        if unique_potion_counts[i] == 0:
            continue
        print({"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]})
        plan.append( {"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]} )

    for index in range(len(ml_types)):
        print(f"{ml_types[index]} used {ml_used[index]-ml_usable[index]}")
    return plan

def update_potion_brew_list():
    """
    Use Current Time To Determine Which Potion To Brew For Next Tick
    """
    """
    Find And Set Potions That Are Popular For Next Tick/ 2 Ticks
    Generate New Potions For Potions That Don't Meet A Specific Threshold Popularity
    """
    return None

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
    ml = [0]*num_types
    total = 100
    if type == 1: 
        index = random.randrange(0,num_types)
        for index in range(num_types-1):
            ml[index] = random.randrange(0,total+1,increment)
            total = total - ml[index]  
            index = (index+1)%4
        ml[index] = total
    elif (type == 2):
        if total%increment != 0:
            ml[random.randrange(0,num_types)] = total%increment
        for _ in range(total//increment):
            ml[random.randrange(0,num_types)] += increment
    else:
        return NotImplemented
    strings = generate_name_sku(ml)
    return {
                "sku":strings["sku"],
                "name":strings["name"],
                "price":price,
                "potion_type":ml
    }

def generate_name_sku(potion_type : list[int]) -> dict[str, str]:
    """
    Generate a simply name and sku with red, green, blue, and dark
    """
    ml_types = ["red", "green", "blue", "dark"]
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
    num_types = 4
    main = potion_type.index(max(potion_type))
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
    str = generate_name_sku(potion_type)
    return {
                "sku":str["sku"],
                "name":str["name"],
                "price":potion["price"],
                "potion_type":potion_type
    }

if __name__ == "__main__":
    new_potion = create_random_potion(7, 1, 25)
    print(new_potion)
    varied_potion = vary_potion(new_potion, 14, 3)
    print(varied_potion)

    #print(get_bottle_plan())