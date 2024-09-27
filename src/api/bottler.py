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
    """ """
    green_pot_cnt = 0
    green_ml_used = 0
    for potion in potions_delivered:
        green_pot_cnt += potion.quantity
        green_ml_used += potion.potion_type[1]*potion.quantity
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions = num_green_potions + {green_pot_cnt}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml - {green_ml_used}"))

    return [
            {
                "potions_delivered": potions_delivered,
                "id": order_id
            }
    ]

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into green potions.
    new_green_pot = 0
    with db.engine.begin() as connection: 
        green_ml_left = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar()
        new_green_pot = green_ml_left//100

    return [
            {
                "potion_type": [0, 100, 0, 0],
                "quantity": new_green_pot
            }
        ]

if __name__ == "__main__":
    print(get_bottle_plan())