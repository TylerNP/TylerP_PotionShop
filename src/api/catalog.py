from fastapi import APIRouter

import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    potions_available = []
    green_pot_cnt = 0
    with db.engine.begin() as connection: 
        potions = connection.execute(sqlalchemy.text("SELECT sku, quantity, price, type FROM potions LIMIT 6"))
        for potion in potions:
            if potion.quantity > 0:
                potions_available.append( {
                    "sku": potion.sku,
                    "name": f"{potion.sku} potion",
                    "quantity": potion.quantity,
                    "price": potion.price,
                    "potion_type": potion.type
                } )
    


    return potions_available
