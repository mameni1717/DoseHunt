// Toutes les clés de la langue, réunies par espace de noms.
import common from "./common.ts";
import home from "./home.ts";
import category from "./category.ts";
import offer from "./offer.ts";
import product from "./product.ts";
import compare from "./compare.ts";
import alerts from "./alerts.ts";
import optimizer from "./optimizer.ts";
import method from "./method.ts";
import legal from "./legal.ts";
import search from "./search.ts";
import cats from "./cats.ts";

const messages = { ...common, ...home, ...category, ...offer, ...product, ...compare, ...alerts, ...optimizer, ...method, ...legal, ...search, ...cats };
export default messages;
