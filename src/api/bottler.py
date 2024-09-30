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
    potions = []
    ml_available = [0]*4
    ml_types = ["red", "green", "blue", "dark"]
    with db.engine.begin() as connection: 
        for index in range(len(ml_types)):
            sql_to_execute = "SELECT num_%s_ml FROM global_inventory"
            ml_available[index] = connection.execute(sqlalchemy.text(sql_to_execute % ml_types[index])).scalar()
        sql_to_execute = "SELECT type, quantity FROM potions"
        potions_brewable = connection.execute(sqlalchemy.text(sql_to_execute))
        for potion in potions_brewable:
            least = -1
            for index in range(len(potion.type)):
                if potion.type[index] > 0:
                    amt = ml_available[index] // potion.type[index]
                    if least == -1 or amt < least:
                        least = amt
            if least > 0:
                potions.append({ "potion_type": potion.type, "quantity": least })

    print(potions)
    return potions

if __name__ == "__main__":
    print(get_bottle_plan())