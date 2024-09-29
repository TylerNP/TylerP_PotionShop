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
    green_pot_cnt = 0
    green_ml_used = 0
    sql_to_execute = ""
    potions_created = []
    with db.engine.begin() as connection:
        for potion in potions_delivered:
            if potion.quantity > 0:
                green_pot_cnt += potion.quantity
                green_ml_used += potion.potion_type[1]*potion.quantity
                postgres_array = '{' + ','.join(map(str, potion.potion_type)) + '}'
                sql_to_execute = "UPDATE potions SET quantity = quantity + %d WHERE type <@ '%s'::int[] AND type @> '%s'::int[]"
                connection.execute(sqlalchemy.text(sql_to_execute % (potion.quantity, postgres_array, postgres_array)))
                potions_created.append( {"potions_delivered": potion.potion_type, "id": order_id} )
        sql_to_execute = "UPDATE global_inventory SET num_potions = num_potions + %d"
        connection.execute(sqlalchemy.text(sql_to_execute % green_pot_cnt))
        sql_to_execute = "UPDATE global_inventory SET num_green_ml = num_green_ml - %d"
        connection.execute(sqlalchemy.text(sql_to_execute % green_ml_used))
    print("used %d mls" % green_ml_used)

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
    new_green_pot = 0
    potions = []
    with db.engine.begin() as connection: 
        green_ml_usable = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar()
        new_green_pot = green_ml_usable//100
        if new_green_pot > 0:
            potions.append( {"potion_type": [0,100,0,0], "quantity": new_green_pot} )


    for potion in potions:
        print(potion)
    return potions

if __name__ == "__main__":
    print(get_bottle_plan())