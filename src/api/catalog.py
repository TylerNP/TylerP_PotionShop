from fastapi import APIRouter

import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    green_pot_cnt = 0
    with db.engine.begin() as connection: 
        green_pot_cnt = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()
        if green_pot_cnt < 0:
            green_pot_cnt = 0


    return [
            {
                "sku": "green",
                "name": "green potion",
                "quantity": green_pot_cnt,
                "price": 100,
                "potion_type": [0, 100, 0, 0]
            }
        ]
