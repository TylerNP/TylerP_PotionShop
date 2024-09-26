from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

with db.engine.begin() as connection: 
    result = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar()

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
    for potion in potions_delivered:
        print(f"potions delievered: {potion.type} order_id: {order_id}")

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into green potions.
    mlLeft = result
    newPot = 0
    while mlLeft >= 100:
        newPot += 1
        mlLeft -= 100

    connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = {mlLeft}"))

    return [
            {
                "potion_type": [0, 100, 0, 0],
                "quantity": newPot,
            }
        ]

if __name__ == "__main__":
    print(get_bottle_plan())