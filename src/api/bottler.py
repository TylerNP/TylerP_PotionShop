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
    sql_to_execute = ""
    potions_created = []
    with db.engine.begin() as connection:
        for potion in potions_delivered:
            if potion.quantity > 0:
                potion_count += potion.quantity
                for index in range(len(potion.potion_type)):
                    ml_used[index] += potion.potion_type[index]*potion.quantity
                sql_to_execute = "UPDATE potions SET quantity = quantity + %d WHERE type[1] = %d AND type[2] = %d AND type[3] = %d AND type[4] = %d"
                connection.execute(sqlalchemy.text(sql_to_execute % (potion.quantity, potion.potion_type[0], potion.potion_type[1], potion.potion_type[2], potion.potion_type[3])))
                potions_created.append( {"potions_delivered": potion.potion_type, "id": order_id} )

        sql_to_execute = "UPDATE global_inventory SET num_potions = num_potions + %d"
        connection.execute(sqlalchemy.text(sql_to_execute % potion_count))
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
    ml_types = ["red", "green", "blue", "dark"]
    unique_potions = []
    with db.engine.begin() as connection: 
        for index in range(len(ml_types)):
            sql_to_execute = "SELECT num_%s_ml FROM global_inventory"
            ml_available[index] = connection.execute(sqlalchemy.text(sql_to_execute % ml_types[index])).scalar()
        sql_to_execute = "SELECT COUNT(1) FROM potions"
        potions_available = connection.execute(sqlalchemy.text(sql_to_execute)).scalar()
        potion_per_capacity = 50
        capacity = connection.execute(sqlalchemy.text("SELECT potion_capacity FROM global_inventory")).scalar()
        potion_capacity = potion_per_capacity * capacity
        potion_threshold = potion_capacity // potions_available
        sql_to_execute = "SELECT type, quantity FROM potions WHERE quantity < %d ORDER BY quantity ASC"
        potions_brewable = connection.execute(sqlalchemy.text(sql_to_execute % potion_threshold))
        unique_potions = [ potion.type for potion in potions_brewable]

    unique_potion_counts = [0]*len(unique_potions)
    done = False
    while unique_potions and not done:
        potion_loop_count = 0
        for potion in unique_potions:
            brewed = True
            ml_leftover = [0]*4
            for index in range(len(potion)):
                ml_leftover[index]= ml_available[index] - potion[index]
                if ml_leftover[index] < 0:
                    brewed = False
                    break

            if brewed:
                ml_available = [ml for ml in ml_leftover]
                unique_potion_counts[unique_potions.index(potion)] += 1
            else:
                potion_loop_count += 1
                full_potion_loop = len(unique_potions)
                if potion_loop_count == full_potion_loop:
                    done = True
                    break

    plan = []
    for i in range(len(unique_potions)):
        if unique_potion_counts[i] == 0:
            continue
        plan.append( {"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]} )
    return plan

if __name__ == "__main__":
    print(get_bottle_plan())