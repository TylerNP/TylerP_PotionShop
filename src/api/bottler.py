from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth

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
    potion_count = 0
    ml_used = [0]*4
    ml_types = ["red", "green", "blue", "dark"]
    potions_created = []
    with db.engine.begin() as connection:
        sql_to_execute = ""
        for potion in potions_delivered:
            if potion.quantity > 0:
                potion_count += potion.quantity
                for index in range(len(potion.potion_type)):
                    ml_used[index] += potion.potion_type[index]*potion.quantity
                sql_to_execute = """
                                    UPDATE potions 
                                    SET quantity = quantity + %d WHERE red = %d AND blue = %d AND green = %d AND dark = %d
                                """
                connection.execute(sqlalchemy.text(sql_to_execute % (potion.quantity, potion.potion_type[0], potion.potion_type[1], potion.potion_type[2], potion.potion_type[3])))
                potions_created.append( {"potions_delivered": potion.potion_type, "id": order_id} )

        sql_to_execute = "UPDATE global_inventory SET num_potions = num_potions + %d"
        connection.execute(sqlalchemy.text(sql_to_execute % potion_count))
        #Replace below with singular sql statement
        for index in range(len(ml_types)):
            if ml_used[index] > 0:
                sql_to_execute = "UPDATE global_inventory SET num_%s_ml = num_%s_ml - %d"
                connection.execute(sqlalchemy.text(sql_to_execute % (ml_types[index], ml_types[index], ml_used[index])))
    print("used %d mls" % (ml_used[0]+ml_used[1]+ml_used[2]+ml_used[3]))

    return potions_created

@router.post("/plan")
def get_bottle_plan():
    """
    Determine what potions to brew from remaining ml 
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into green potions.
    ml_available = [0]*4
    ml_max = [0]*4
    ml_types = ["red", "green", "blue", "dark"]
    unique_potions = []
    potion_brew_amount = []
    with db.engine.begin() as connection: 
        # Combine With Potions Query As Subquery LATER
        sql_to_execute = "SELECT potion_capacity, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory"
        results = connection.execute(sqlalchemy.text(sql_to_execute))
        capacity = 0
        for result in results:
            ml_available[0] = result.num_red_ml
            ml_available[1] = result.num_green_ml
            ml_available[2] = result.num_blue_ml
            ml_available[3] = result.num_dark_ml
            capacity = result.potion_capacity

        sql_to_execute = "SELECT COUNT(1) FROM potions"
        potions_available = connection.execute(sqlalchemy.text(sql_to_execute)).scalar()
        potion_per_capacity = 50
        potion_capacity = potion_per_capacity * capacity
        potion_threshold = potion_capacity // potions_available
        sql_to_execute = """
                            SELECT red, green, blue, dark, quantity 
                            FROM potions 
                            WHERE quantity < %d AND red <= %d AND green <= %d AND blue <= %d AND dark <= %d 
                            ORDER BY quantity ASC, price DESC
                        """
        potions_brewable = connection.execute(sqlalchemy.text(sql_to_execute % (potion_threshold,ml_available[0], ml_available[1], ml_available[2], ml_available[3] )))
        for potion in potions_brewable:
            unique_potions.append([potion.red, potion.green, potion.blue, potion.dark])
            desired_potion_brew_count = potion_threshold-potion.quantity
            potion_brew_amount.append(desired_potion_brew_count)
            ml_max[0] += potion.red*desired_potion_brew_count
            ml_max[1] += potion.blue*desired_potion_brew_count
            ml_max[2] += potion.green*desired_potion_brew_count
            ml_max[3] += potion.dark*desired_potion_brew_count

    if not potion_brew_amount:
        return []
    min = potion_brew_amount[-1]
    potion_brew_ratio = [ round(quantity/min) for quantity in potion_brew_amount]
    brew_ratio_copy = potion_brew_ratio.copy()
    ml_usable = [ ml_available[index] if ml_available[index] < ml_max[index] else ml_max[index] for index in range(len(ml_max))]
    ml_used = ml_usable.copy()
    unique_potion_counts = [0]*len(unique_potions)
    potion_index = 0
    potion_count = len(unique_potions)
    potion_unavailable = [0]*potion_count
    count = 0
    loop_count = 0
    while True:
        count += 1
        if all (potion_unavailable):
            break
        if not any(brew_ratio_copy):
            brew_ratio_copy = potion_brew_ratio.copy()
        if brew_ratio_copy[potion_index] == 0 or potion_unavailable[potion_index] == 1:
            potion_index = (potion_index+1)%potion_count
            loop_count = loop_count + 1
            if loop_count > potion_count:
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
        ml_usable = [ml for ml in ml_leftover]
        unique_potion_counts[potion_index] += 1
        brew_ratio_copy[potion_index] -= 1
        if potion_brew_amount[potion_index] == unique_potion_counts[potion_index]:
            potion_unavailable[potion_index] = 1
        potion_index = (potion_index+1)%len(unique_potions)

    plan = []
    for i in range(len(unique_potions)):
        if unique_potion_counts[i] == 0:
            continue
        print({"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]})
        plan.append( {"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]} )

    print(count)
    for index in range(len(ml_types)):
        print(f"{ml_types[index]} used {ml_used[index]-ml_usable[index]}")
    return plan

if __name__ == "__main__":
    print(get_bottle_plan())