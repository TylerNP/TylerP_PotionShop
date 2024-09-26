from fastapi import APIRouter

import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    with db.engine.begin() as connection: 
        greenPotCnt = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()

    return [
            {
                "sku": "GREEN_POTION_0",
                "name": "green potion",
                "quantity": greenPotCnt,
                "price": 50,
                "potion_type": [0, 100, 0, 0],
            }
        ]
