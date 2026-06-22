/**
 * nutritionist_data.ts — Seed data for the Nutritionist Dashboard backend.
 *
 * All values per 100 g edible portion (USDA FDC + INA Tunisienne where
 * applicable). region: "NA" = North African staple, "GL" = global staple,
 * "BOTH" = ubiquitous.
 */

export type Tier = "HIGH" | "MEDIUM" | "LOW" | "SAFE";

export type FoodSeed = {
  food_key: string;
  name_fr: string;
  name_en: string;
  name_ar: string;
  category: string;
  vitamin_k_mcg: number;
  iron_mg: number;
  vitamin_d_iu: number;
  calcium_mg: number;
  b12_mcg: number;
  region: "NA" | "GL" | "BOTH";
};

export const FOODS: FoodSeed[] = [
  // Leafy greens (high Vit K)
  { food_key: "spinach",     name_fr: "Épinards",       name_en: "Spinach",          name_ar: "سبانخ",          category: "leafy_green_high_k", vitamin_k_mcg: 483, iron_mg: 2.7, vitamin_d_iu: 0,   calcium_mg: 99,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "kale",        name_fr: "Chou frisé",     name_en: "Kale",             name_ar: "كرنب أجعد",      category: "leafy_green_high_k", vitamin_k_mcg: 705, iron_mg: 1.5, vitamin_d_iu: 0,   calcium_mg: 150, b12_mcg: 0,   region: "GL" },
  { food_key: "swiss_chard", name_fr: "Bette à carde",  name_en: "Swiss chard",      name_ar: "سلق",            category: "leafy_green_high_k", vitamin_k_mcg: 830, iron_mg: 1.8, vitamin_d_iu: 0,   calcium_mg: 51,  b12_mcg: 0,   region: "NA"   },
  { food_key: "parsley",     name_fr: "Persil",         name_en: "Parsley",          name_ar: "معدنوس",         category: "herb_high_k",        vitamin_k_mcg: 1640,iron_mg: 6.2, vitamin_d_iu: 0,   calcium_mg: 138, b12_mcg: 0,   region: "BOTH" },
  { food_key: "coriander",   name_fr: "Coriandre",      name_en: "Coriander",        name_ar: "قزبر",           category: "herb_high_k",        vitamin_k_mcg: 310, iron_mg: 1.8, vitamin_d_iu: 0,   calcium_mg: 67,  b12_mcg: 0,   region: "NA"   },
  { food_key: "mint",        name_fr: "Menthe",         name_en: "Mint",             name_ar: "نعناع",          category: "herb_medium_k",      vitamin_k_mcg: 11,  iron_mg: 5.1, vitamin_d_iu: 0,   calcium_mg: 199, b12_mcg: 0,   region: "NA"   },
  { food_key: "lettuce",     name_fr: "Laitue",         name_en: "Lettuce",          name_ar: "خس",             category: "leafy_green_medium_k",vitamin_k_mcg: 102,iron_mg: 0.9, vitamin_d_iu: 0,   calcium_mg: 36,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "purslane",    name_fr: "Pourpier",       name_en: "Purslane",         name_ar: "البقلة",         category: "leafy_green_high_k", vitamin_k_mcg: 381, iron_mg: 2.0, vitamin_d_iu: 0,   calcium_mg: 65,  b12_mcg: 0,   region: "NA"   },
  { food_key: "mloukhia",    name_fr: "Mloukhia",       name_en: "Jute mallow",      name_ar: "ملوخية",         category: "leafy_green_high_k", vitamin_k_mcg: 405, iron_mg: 4.8, vitamin_d_iu: 0,   calcium_mg: 184, b12_mcg: 0,   region: "NA"   },
  { food_key: "arugula",     name_fr: "Roquette",       name_en: "Arugula",          name_ar: "جرجير",          category: "leafy_green_medium_k",vitamin_k_mcg: 109,iron_mg: 1.5, vitamin_d_iu: 0,   calcium_mg: 160, b12_mcg: 0,   region: "BOTH" },
  // Low-K vegetables
  { food_key: "iceberg",     name_fr: "Laitue iceberg", name_en: "Iceberg lettuce",  name_ar: "خس آيسبرغ",      category: "leafy_green_low_k",  vitamin_k_mcg: 24,  iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 18,  b12_mcg: 0,   region: "GL"   },
  { food_key: "cucumber",    name_fr: "Concombre",      name_en: "Cucumber",         name_ar: "خيار",           category: "vegetable_low_k",    vitamin_k_mcg: 16,  iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 16,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "tomato",      name_fr: "Tomate",         name_en: "Tomato",           name_ar: "طماطم",          category: "vegetable_low_k",    vitamin_k_mcg: 7,   iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 10,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "bell_pepper", name_fr: "Poivron",        name_en: "Bell pepper",      name_ar: "فلفل حلو",       category: "vegetable_low_k",    vitamin_k_mcg: 5,   iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 7,   b12_mcg: 0,   region: "BOTH" },
  { food_key: "zucchini",    name_fr: "Courgette",      name_en: "Zucchini",         name_ar: "قرع",            category: "vegetable_low_k",    vitamin_k_mcg: 4.3, iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 16,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "eggplant",    name_fr: "Aubergine",      name_en: "Eggplant",         name_ar: "باذنجان",        category: "vegetable_low_k",    vitamin_k_mcg: 3.5, iron_mg: 0.2, vitamin_d_iu: 0,   calcium_mg: 9,   b12_mcg: 0,   region: "NA"   },
  { food_key: "okra",        name_fr: "Gombo",          name_en: "Okra",             name_ar: "بامية",          category: "vegetable_medium_k", vitamin_k_mcg: 32,  iron_mg: 0.6, vitamin_d_iu: 0,   calcium_mg: 82,  b12_mcg: 0,   region: "NA"   },
  { food_key: "onion",       name_fr: "Oignon",         name_en: "Onion",            name_ar: "بصل",            category: "vegetable_low_k",    vitamin_k_mcg: 0.4, iron_mg: 0.2, vitamin_d_iu: 0,   calcium_mg: 23,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "garlic",      name_fr: "Ail",            name_en: "Garlic",           name_ar: "ثوم",            category: "vegetable_low_k",    vitamin_k_mcg: 1.7, iron_mg: 1.7, vitamin_d_iu: 0,   calcium_mg: 181, b12_mcg: 0,   region: "BOTH" },
  { food_key: "pumpkin",     name_fr: "Citrouille",     name_en: "Pumpkin",          name_ar: "يقطين",          category: "vegetable_low_k",    vitamin_k_mcg: 1.1, iron_mg: 0.8, vitamin_d_iu: 0,   calcium_mg: 21,  b12_mcg: 0,   region: "BOTH" },
  // Cruciferous
  { food_key: "broccoli",    name_fr: "Brocoli",        name_en: "Broccoli",         name_ar: "بروكلي",         category: "cruciferous_medium_k",vitamin_k_mcg: 102,iron_mg: 0.7, vitamin_d_iu: 0,   calcium_mg: 47,  b12_mcg: 0,   region: "GL"   },
  { food_key: "cauliflower", name_fr: "Chou-fleur",     name_en: "Cauliflower",      name_ar: "قرنبيط",         category: "cruciferous_low_k",  vitamin_k_mcg: 16,  iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 22,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "cabbage",     name_fr: "Chou",           name_en: "Cabbage",          name_ar: "ملفوف",          category: "cruciferous_medium_k",vitamin_k_mcg: 76, iron_mg: 0.5, vitamin_d_iu: 0,   calcium_mg: 40,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "brussels",    name_fr: "Choux de Bruxelles",name_en:"Brussels sprouts",name_ar:"كرنب بروكسل",     category: "cruciferous_high_k", vitamin_k_mcg: 177, iron_mg: 1.4, vitamin_d_iu: 0,   calcium_mg: 42,  b12_mcg: 0,   region: "GL"   },
  // Roots
  { food_key: "carrot",      name_fr: "Carotte",        name_en: "Carrot",           name_ar: "جزر",            category: "root_low_k",         vitamin_k_mcg: 13,  iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 33,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "turnip",      name_fr: "Navet",          name_en: "Turnip",           name_ar: "لفت",            category: "root_low_k",         vitamin_k_mcg: 0.1, iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 30,  b12_mcg: 0,   region: "NA"   },
  { food_key: "potato",      name_fr: "Pomme de terre", name_en: "Potato",           name_ar: "بطاطا",          category: "root_low_k",         vitamin_k_mcg: 2,   iron_mg: 0.8, vitamin_d_iu: 0,   calcium_mg: 12,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "sweet_potato",name_fr: "Patate douce",   name_en: "Sweet potato",     name_ar: "بطاطا حلوة",     category: "root_low_k",         vitamin_k_mcg: 1.8, iron_mg: 0.6, vitamin_d_iu: 0,   calcium_mg: 30,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "beet",        name_fr: "Betterave",      name_en: "Beetroot",         name_ar: "شمندر",          category: "root_low_k",         vitamin_k_mcg: 0.2, iron_mg: 0.8, vitamin_d_iu: 0,   calcium_mg: 16,  b12_mcg: 0,   region: "BOTH" },
  // Legumes
  { food_key: "chickpea",    name_fr: "Pois chiche",    name_en: "Chickpeas",        name_ar: "حمص",            category: "legume",             vitamin_k_mcg: 9,   iron_mg: 2.9, vitamin_d_iu: 0,   calcium_mg: 49,  b12_mcg: 0,   region: "NA"   },
  { food_key: "lentil",      name_fr: "Lentilles",      name_en: "Lentils",          name_ar: "عدس",            category: "legume",             vitamin_k_mcg: 1.7, iron_mg: 3.3, vitamin_d_iu: 0,   calcium_mg: 19,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "fava",        name_fr: "Fève",           name_en: "Fava bean",        name_ar: "فول",            category: "legume",             vitamin_k_mcg: 5,   iron_mg: 1.5, vitamin_d_iu: 0,   calcium_mg: 36,  b12_mcg: 0,   region: "NA"   },
  { food_key: "white_bean",  name_fr: "Haricot blanc",  name_en: "White bean",       name_ar: "لوبيا بيضاء",    category: "legume",             vitamin_k_mcg: 5.6, iron_mg: 3.7, vitamin_d_iu: 0,   calcium_mg: 90,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "green_pea",   name_fr: "Petits pois",    name_en: "Green peas",       name_ar: "بازلاء",         category: "legume_medium_k",    vitamin_k_mcg: 24,  iron_mg: 1.5, vitamin_d_iu: 0,   calcium_mg: 25,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "green_bean",  name_fr: "Haricot vert",   name_en: "Green bean",       name_ar: "فاصوليا خضراء",  category: "legume_medium_k",    vitamin_k_mcg: 43,  iron_mg: 1.0, vitamin_d_iu: 0,   calcium_mg: 37,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "soybean",     name_fr: "Soja",           name_en: "Soybean",          name_ar: "صويا",           category: "legume_high_k",      vitamin_k_mcg: 47,  iron_mg: 8.8, vitamin_d_iu: 0,   calcium_mg: 102, b12_mcg: 0,   region: "GL"   },
  // Grains
  { food_key: "semolina",       name_fr: "Semoule",     name_en: "Semolina",         name_ar: "سميد",           category: "grain",              vitamin_k_mcg: 0,   iron_mg: 1.2, vitamin_d_iu: 0,   calcium_mg: 17,  b12_mcg: 0,   region: "NA"   },
  { food_key: "bulgur",         name_fr: "Boulgour",    name_en: "Bulgur",           name_ar: "برغل",           category: "grain",              vitamin_k_mcg: 0.5, iron_mg: 1.0, vitamin_d_iu: 0,   calcium_mg: 10,  b12_mcg: 0,   region: "NA"   },
  { food_key: "frik",           name_fr: "Frik",        name_en: "Freekeh",          name_ar: "فريك",           category: "grain",              vitamin_k_mcg: 0,   iron_mg: 2.2, vitamin_d_iu: 0,   calcium_mg: 35,  b12_mcg: 0,   region: "NA"   },
  { food_key: "rice_white",     name_fr: "Riz blanc",   name_en: "White rice",       name_ar: "أرز أبيض",       category: "grain",              vitamin_k_mcg: 0,   iron_mg: 0.2, vitamin_d_iu: 0,   calcium_mg: 10,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "rice_brown",     name_fr: "Riz complet", name_en: "Brown rice",       name_ar: "أرز بني",        category: "grain",              vitamin_k_mcg: 0.6, iron_mg: 0.5, vitamin_d_iu: 0,   calcium_mg: 10,  b12_mcg: 0,   region: "GL"   },
  { food_key: "barley",         name_fr: "Orge",        name_en: "Barley",           name_ar: "شعير",           category: "grain",              vitamin_k_mcg: 2.2, iron_mg: 2.5, vitamin_d_iu: 0,   calcium_mg: 33,  b12_mcg: 0,   region: "NA"   },
  { food_key: "oat",            name_fr: "Avoine",      name_en: "Oats",             name_ar: "شوفان",          category: "grain",              vitamin_k_mcg: 2,   iron_mg: 4.7, vitamin_d_iu: 0,   calcium_mg: 54,  b12_mcg: 0,   region: "GL"   },
  { food_key: "khobz_dar",      name_fr: "Khobz dar",   name_en: "Algerian bread",   name_ar: "خبز الدار",      category: "grain",              vitamin_k_mcg: 1,   iron_mg: 2.0, vitamin_d_iu: 0,   calcium_mg: 30,  b12_mcg: 0,   region: "NA"   },
  { food_key: "msemen",         name_fr: "Msemen",      name_en: "Msemen pancake",   name_ar: "مسمن",           category: "grain",              vitamin_k_mcg: 2,   iron_mg: 1.5, vitamin_d_iu: 0,   calcium_mg: 40,  b12_mcg: 0,   region: "NA"   },
  { food_key: "matlou3",        name_fr: "Matlou3",     name_en: "Matlou3 bread",    name_ar: "مطلوع",          category: "grain",              vitamin_k_mcg: 0.5, iron_mg: 1.8, vitamin_d_iu: 0,   calcium_mg: 25,  b12_mcg: 0,   region: "NA"   },
  { food_key: "couscous_grain", name_fr: "Couscous (grain)", name_en: "Couscous grain", name_ar: "كسكسي حب",    category: "grain",              vitamin_k_mcg: 0,   iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 8,   b12_mcg: 0,   region: "NA"   },
  // Meat & fish
  { food_key: "lamb",        name_fr: "Agneau",         name_en: "Lamb",             name_ar: "لحم خروف",       category: "meat_red",           vitamin_k_mcg: 4,   iron_mg: 1.9, vitamin_d_iu: 0,   calcium_mg: 17,  b12_mcg: 2.7, region: "NA"   },
  { food_key: "beef",        name_fr: "Bœuf",           name_en: "Beef",             name_ar: "لحم بقر",        category: "meat_red",           vitamin_k_mcg: 1.5, iron_mg: 2.6, vitamin_d_iu: 7,   calcium_mg: 12,  b12_mcg: 2.6, region: "BOTH" },
  { food_key: "chicken",     name_fr: "Poulet",         name_en: "Chicken",          name_ar: "دجاج",           category: "meat_white",         vitamin_k_mcg: 2.4, iron_mg: 0.9, vitamin_d_iu: 5,   calcium_mg: 15,  b12_mcg: 0.3, region: "BOTH" },
  { food_key: "turkey",      name_fr: "Dinde",          name_en: "Turkey",           name_ar: "حبش",            category: "meat_white",         vitamin_k_mcg: 0.1, iron_mg: 1.4, vitamin_d_iu: 30,  calcium_mg: 21,  b12_mcg: 1.6, region: "GL"   },
  { food_key: "merguez",     name_fr: "Merguez",        name_en: "Merguez",          name_ar: "مرڨاز",          category: "meat_red_processed", vitamin_k_mcg: 1,   iron_mg: 2.1, vitamin_d_iu: 5,   calcium_mg: 20,  b12_mcg: 1.5, region: "NA"   },
  { food_key: "liver_beef",  name_fr: "Foie de bœuf",   name_en: "Beef liver",       name_ar: "كبدة",           category: "offal",              vitamin_k_mcg: 3.1, iron_mg: 6.5, vitamin_d_iu: 49,  calcium_mg: 5,   b12_mcg: 70,  region: "BOTH" },
  { food_key: "sardine",     name_fr: "Sardine",        name_en: "Sardine",          name_ar: "سردين",          category: "fish_oily",          vitamin_k_mcg: 2.6, iron_mg: 2.9, vitamin_d_iu: 193, calcium_mg: 382, b12_mcg: 8.9, region: "NA"   },
  { food_key: "tuna",        name_fr: "Thon",           name_en: "Tuna",             name_ar: "تونة",           category: "fish_oily",          vitamin_k_mcg: 0.1, iron_mg: 1.0, vitamin_d_iu: 269, calcium_mg: 8,   b12_mcg: 9.4, region: "BOTH" },
  { food_key: "salmon",      name_fr: "Saumon",         name_en: "Salmon",           name_ar: "سلمون",          category: "fish_oily",          vitamin_k_mcg: 0.1, iron_mg: 0.3, vitamin_d_iu: 526, calcium_mg: 9,   b12_mcg: 3.2, region: "GL"   },
  { food_key: "egg",         name_fr: "Œuf",            name_en: "Egg",              name_ar: "بيض",            category: "egg",                vitamin_k_mcg: 0.3, iron_mg: 1.8, vitamin_d_iu: 87,  calcium_mg: 56,  b12_mcg: 0.9, region: "BOTH" },
  // Dairy
  { food_key: "milk_cow",    name_fr: "Lait de vache",  name_en: "Cow milk",         name_ar: "حليب البقر",     category: "dairy",              vitamin_k_mcg: 0.3, iron_mg: 0.0, vitamin_d_iu: 47,  calcium_mg: 113, b12_mcg: 0.5, region: "BOTH" },
  { food_key: "yogurt",      name_fr: "Yaourt",         name_en: "Yogurt",           name_ar: "زبادي",          category: "dairy",              vitamin_k_mcg: 0.2, iron_mg: 0.1, vitamin_d_iu: 0,   calcium_mg: 121, b12_mcg: 0.5, region: "BOTH" },
  { food_key: "lben",        name_fr: "Lben",           name_en: "Lben",             name_ar: "لبن",            category: "dairy",              vitamin_k_mcg: 0.1, iron_mg: 0.0, vitamin_d_iu: 0,   calcium_mg: 110, b12_mcg: 0.4, region: "NA"   },
  { food_key: "cheese_white",name_fr: "Fromage blanc",  name_en: "Fresh cheese",     name_ar: "جبن أبيض",       category: "dairy",              vitamin_k_mcg: 1,   iron_mg: 0.2, vitamin_d_iu: 7,   calcium_mg: 200, b12_mcg: 0.7, region: "BOTH" },
  { food_key: "raib",        name_fr: "Raïb",           name_en: "Raïb",             name_ar: "رايب",           category: "dairy",              vitamin_k_mcg: 0.2, iron_mg: 0.0, vitamin_d_iu: 0,   calcium_mg: 130, b12_mcg: 0.4, region: "NA"   },
  // Fruits
  { food_key: "date",        name_fr: "Datte",          name_en: "Dates",            name_ar: "تمر",            category: "fruit_dried",        vitamin_k_mcg: 2.7, iron_mg: 1.0, vitamin_d_iu: 0,   calcium_mg: 39,  b12_mcg: 0,   region: "NA"   },
  { food_key: "fig",         name_fr: "Figue",          name_en: "Fig",              name_ar: "تين",            category: "fruit_fresh",        vitamin_k_mcg: 4.7, iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 35,  b12_mcg: 0,   region: "NA"   },
  { food_key: "orange",      name_fr: "Orange",         name_en: "Orange",           name_ar: "برتقال",         category: "fruit_citrus",       vitamin_k_mcg: 0,   iron_mg: 0.1, vitamin_d_iu: 0,   calcium_mg: 40,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "lemon",       name_fr: "Citron",         name_en: "Lemon",            name_ar: "ليمون",          category: "fruit_citrus",       vitamin_k_mcg: 0,   iron_mg: 0.6, vitamin_d_iu: 0,   calcium_mg: 26,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "grapefruit",  name_fr: "Pamplemousse",   name_en: "Grapefruit",       name_ar: "ليمون هندي",     category: "fruit_citrus_high_risk",vitamin_k_mcg:0,iron_mg: 0.1, vitamin_d_iu: 0,   calcium_mg: 22,  b12_mcg: 0,   region: "GL"   },
  { food_key: "apple",       name_fr: "Pomme",          name_en: "Apple",            name_ar: "تفاح",           category: "fruit_fresh",        vitamin_k_mcg: 2.2, iron_mg: 0.1, vitamin_d_iu: 0,   calcium_mg: 6,   b12_mcg: 0,   region: "BOTH" },
  { food_key: "banana",      name_fr: "Banane",         name_en: "Banana",           name_ar: "موز",            category: "fruit_fresh",        vitamin_k_mcg: 0.5, iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 5,   b12_mcg: 0,   region: "BOTH" },
  { food_key: "pomegranate", name_fr: "Grenade",        name_en: "Pomegranate",      name_ar: "رمان",           category: "fruit_fresh",        vitamin_k_mcg: 16,  iron_mg: 0.3, vitamin_d_iu: 0,   calcium_mg: 10,  b12_mcg: 0,   region: "NA"   },
  { food_key: "watermelon",  name_fr: "Pastèque",       name_en: "Watermelon",       name_ar: "دلاع",           category: "fruit_fresh",        vitamin_k_mcg: 0.1, iron_mg: 0.2, vitamin_d_iu: 0,   calcium_mg: 7,   b12_mcg: 0,   region: "NA"   },
  { food_key: "olive_green", name_fr: "Olive verte",    name_en: "Green olive",      name_ar: "زيتون أخضر",     category: "fruit_oily",         vitamin_k_mcg: 1.4, iron_mg: 0.5, vitamin_d_iu: 0,   calcium_mg: 52,  b12_mcg: 0,   region: "NA"   },
  { food_key: "olive_oil",   name_fr: "Huile d'olive",  name_en: "Olive oil",        name_ar: "زيت الزيتون",    category: "oil",                vitamin_k_mcg: 60,  iron_mg: 0.6, vitamin_d_iu: 0,   calcium_mg: 1,   b12_mcg: 0,   region: "NA"   },
  // Nuts & seeds
  { food_key: "almond",      name_fr: "Amande",         name_en: "Almond",           name_ar: "لوز",            category: "nut",                vitamin_k_mcg: 0,   iron_mg: 3.7, vitamin_d_iu: 0,   calcium_mg: 269, b12_mcg: 0,   region: "BOTH" },
  { food_key: "walnut",      name_fr: "Noix",           name_en: "Walnut",           name_ar: "جوز",            category: "nut",                vitamin_k_mcg: 2.7, iron_mg: 2.9, vitamin_d_iu: 0,   calcium_mg: 98,  b12_mcg: 0,   region: "BOTH" },
  { food_key: "pistachio",   name_fr: "Pistache",       name_en: "Pistachio",        name_ar: "فستق",           category: "nut",                vitamin_k_mcg: 13,  iron_mg: 3.9, vitamin_d_iu: 0,   calcium_mg: 105, b12_mcg: 0,   region: "BOTH" },
  { food_key: "sesame",      name_fr: "Sésame",         name_en: "Sesame",           name_ar: "سمسم",           category: "seed",               vitamin_k_mcg: 0,   iron_mg: 14.6,vitamin_d_iu: 0,   calcium_mg: 975, b12_mcg: 0,   region: "NA"   },
  { food_key: "peanut",      name_fr: "Cacahuète",      name_en: "Peanut",           name_ar: "فول السوداني",   category: "nut",                vitamin_k_mcg: 0,   iron_mg: 4.6, vitamin_d_iu: 0,   calcium_mg: 92,  b12_mcg: 0,   region: "BOTH" },
  // Beverages & condiments
  { food_key: "tea_green",   name_fr: "Thé vert",       name_en: "Green tea",        name_ar: "شاي أخضر",       category: "beverage_tannin",    vitamin_k_mcg: 0,   iron_mg: 0,   vitamin_d_iu: 0,   calcium_mg: 0,   b12_mcg: 0,   region: "BOTH" },
  { food_key: "tea_mint",    name_fr: "Thé à la menthe",name_en: "Mint tea",         name_ar: "أتاي بالنعناع",  category: "beverage_tannin",    vitamin_k_mcg: 0,   iron_mg: 0,   vitamin_d_iu: 0,   calcium_mg: 0,   b12_mcg: 0,   region: "NA"   },
  { food_key: "coffee",      name_fr: "Café",           name_en: "Coffee",           name_ar: "قهوة",           category: "beverage_caffeine",  vitamin_k_mcg: 0.1, iron_mg: 0,   vitamin_d_iu: 0,   calcium_mg: 2,   b12_mcg: 0,   region: "BOTH" },
  { food_key: "honey",       name_fr: "Miel",           name_en: "Honey",            name_ar: "عسل",            category: "sweetener",          vitamin_k_mcg: 0,   iron_mg: 0.4, vitamin_d_iu: 0,   calcium_mg: 6,   b12_mcg: 0,   region: "NA"   },
  { food_key: "harissa",     name_fr: "Harissa",        name_en: "Harissa",          name_ar: "هريسة",          category: "condiment",          vitamin_k_mcg: 8,   iron_mg: 2.0, vitamin_d_iu: 0,   calcium_mg: 25,  b12_mcg: 0,   region: "NA"   },
  { food_key: "tomato_paste",name_fr: "Concentré de tomate", name_en:"Tomato paste", name_ar: "صلصة الطماطم",   category: "condiment",          vitamin_k_mcg: 16,  iron_mg: 2.8, vitamin_d_iu: 0,   calcium_mg: 36,  b12_mcg: 0,   region: "NA"   },
];

// ── Substitute groups ──────────────────────────────────────────────────────
export const SUB_GROUPS: Record<string, string[]> = {
  greens_low_k:        ["zucchini", "eggplant", "okra", "cucumber", "bell_pepper", "iceberg"],
  greens_high_k:       ["spinach", "kale", "swiss_chard", "parsley", "purslane", "mloukhia"],
  greens_medium_k:     ["lettuce", "arugula", "cabbage", "broccoli"],
  cruciferous_low_k:   ["cauliflower", "zucchini", "carrot"],
  root_starchy:        ["potato", "sweet_potato", "turnip", "beet", "carrot"],
  red_meat:            ["lamb", "beef", "merguez"],
  white_meat:          ["chicken", "turkey"],
  oily_fish:           ["sardine", "tuna", "salmon"],
  grain_low_k:         ["semolina", "couscous_grain", "rice_white", "rice_brown", "bulgur", "frik", "barley", "khobz_dar", "matlou3"],
  dairy_calcium:       ["yogurt", "lben", "raib", "cheese_white", "milk_cow"],
  fruit_low_k:         ["orange", "lemon", "apple", "banana", "watermelon"],
  fruit_high_iron:     ["date", "fig", "pomegranate"],
  citrus_low_risk:     ["orange", "lemon"],
};

export const FOOD_TO_GROUPS: Record<string, string[]> = (() => {
  const map: Record<string, string[]> = {};
  for (const [g, foods] of Object.entries(SUB_GROUPS)) {
    for (const f of foods) (map[f] = map[f] || []).push(g);
  }
  return map;
})();

// ── Dish recipes (manual templates) ────────────────────────────────────────
export const DISH_RECIPES: Record<string, { name_en: string; name_fr: string; name_ar: string; components: string[] }> = {
  couscous:        { name_en: "Couscous",        name_fr: "Couscous",        name_ar: "كسكسي",        components: ["couscous_grain", "chickpea", "carrot", "turnip", "zucchini", "pumpkin", "lamb", "tomato_paste", "olive_oil"] },
  chorba_frik:     { name_en: "Chorba frik",     name_fr: "Chorba frik",     name_ar: "شربة فريك",     components: ["frik", "lamb", "tomato", "onion", "chickpea", "coriander", "mint", "olive_oil"] },
  chakhchoukha:    { name_en: "Chakhchoukha",    name_fr: "Chakhchoukha",    name_ar: "شخشوخة",        components: ["semolina", "lamb", "tomato", "chickpea", "carrot", "turnip", "harissa"] },
  rechta:          { name_en: "Rechta",          name_fr: "Rechta",          name_ar: "رشتة",          components: ["semolina", "chicken", "chickpea", "turnip", "onion"] },
  mhajeb:          { name_en: "Mhadjeb",         name_fr: "Mhadjeb",         name_ar: "محاجب",         components: ["semolina", "tomato", "onion", "bell_pepper", "olive_oil"] },
  mloukhia_dish:   { name_en: "Mloukhia",        name_fr: "Mloukhia",        name_ar: "ملوخية",        components: ["mloukhia", "beef", "tomato_paste", "garlic", "coriander"] },
  dolma:           { name_en: "Dolma",           name_fr: "Dolma",           name_ar: "دولمة",         components: ["zucchini", "potato", "bell_pepper", "tomato", "beef", "rice_white", "parsley"] },
  brik:            { name_en: "Brik",            name_fr: "Brik",            name_ar: "بريك",          components: ["semolina", "egg", "tuna", "parsley", "onion"] },
  tajine_zitoune:  { name_en: "Tajine zitoune",  name_fr: "Tajine zitoune",  name_ar: "طاجين زيتون",   components: ["chicken", "olive_green", "carrot", "lemon", "olive_oil"] },
  tajine_hlou:     { name_en: "Tajine hlou",     name_fr: "Tajine hlou",     name_ar: "طاجين حلو",     components: ["lamb", "date", "almond", "pomegranate", "honey"] },
  shakshouka:      { name_en: "Shakshouka",      name_fr: "Chakchouka",      name_ar: "شكشوكة",        components: ["tomato", "bell_pepper", "egg", "onion", "olive_oil", "harissa"] },
  hmiss:           { name_en: "Hmiss",           name_fr: "Hmiss",           name_ar: "حميص",          components: ["tomato", "bell_pepper", "garlic", "olive_oil"] },
  bourek:          { name_en: "Bourek",          name_fr: "Bourek",          name_ar: "بورك",          components: ["semolina", "beef", "onion", "egg", "parsley"] },
  hrira:           { name_en: "Hrira",           name_fr: "Hrira",           name_ar: "حريرة",         components: ["lentil", "chickpea", "tomato", "coriander", "lamb"] },
  loubia:          { name_en: "Loubia",          name_fr: "Loubia",          name_ar: "لوبيا",         components: ["white_bean", "tomato", "garlic", "olive_oil", "coriander"] },
  zviti:           { name_en: "Zviti",           name_fr: "Zviti",           name_ar: "زفيتي",         components: ["semolina", "harissa", "olive_oil", "garlic", "lemon"] },
  lham_lahlou:     { name_en: "Lham lahlou",     name_fr: "Lham lahlou",     name_ar: "لحم حلو",       components: ["lamb", "date", "pomegranate", "almond", "honey"] },
  salade_mechouia: { name_en: "Salade mechouia", name_fr: "Salade mechouia", name_ar: "سلطة مشوية",    components: ["bell_pepper", "tomato", "garlic", "olive_oil"] },
  salade_carotte:  { name_en: "Carrot salad",    name_fr: "Salade de carotte",name_ar: "سلطة جزر",     components: ["carrot", "lemon", "olive_oil", "coriander"] },
  ftour:           { name_en: "Algerian ftour",  name_fr: "Petit-déjeuner",  name_ar: "فطور",          components: ["khobz_dar", "olive_oil", "olive_green", "cheese_white", "tea_mint"] },
  baghrir:         { name_en: "Baghrir",         name_fr: "Baghrir",         name_ar: "بغرير",         components: ["semolina", "honey"] },
};

// ── Biomarker synergy rules ────────────────────────────────────────────────
export type SynergyRule = {
  id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  drug_match: RegExp;
  lab_signals: RegExp[];
  title:  { fr: string; en: string; ar: string };
  advice: { fr: string[]; en: string[]; ar: string[] };
};

export const SYNERGY_RULES: SynergyRule[] = [
  {
    id: "ppi_iron", severity: "HIGH",
    drug_match: /omepraz|esomepraz|pantopraz|lansopraz|rabepraz|inipomp|mopral/i,
    lab_signals: [/iron/i, /ferrit/i],
    title: { fr: "Conflit d'absorption du fer (IPP + carence)", en: "Iron absorption conflict (PPI + iron deficiency)", ar: "تعارض امتصاص الحديد (IPP + نقص الحديد)" },
    advice: {
      fr: ["Ajouter vitamine C (citron, tomate, orange) aux repas ferreux.", "Programmer les repas riches en fer 3 h après la prise de l'IPP.", "Éviter thé, café, laitages dans l'heure des repas ferreux."],
      en: ["Add vitamin-C-rich foods (lemon, tomato, orange) to iron-rich meals.", "Schedule iron-rich meals 3+ hours after the PPI dose.", "Avoid tea, coffee, and dairy within 1 hour of iron-rich meals."],
      ar: ["أضف أطعمة غنية بفيتامين C (ليمون، طماطم، برتقال).", "تناول الوجبات الحديدية بعد 3 ساعات من جرعة الدواء.", "تجنّب الشاي والقهوة والألبان خلال ساعة من الوجبة."],
    },
  },
  {
    id: "warfarin_vitk", severity: "HIGH",
    drug_match: /warfarin|sintrom|acenocoum|coumadin/i,
    lab_signals: [/vitamin\s*k/i, /vitk/i, /phylloquinone/i, /menaquinone/i],
    title: { fr: "Anticoagulant + apport en vitamine K", en: "Anticoagulant + Vitamin K intake", ar: "مضاد التخثر + فيتامين K" },
    advice: {
      fr: ["Garder l'apport en légumes verts CONSTANT d'un jour à l'autre.", "Cible : ~90–120 µg/j. Au-delà de 250 µg/j : risque d'instabilité de l'INR.", "Préférer courgette, aubergine, carotte aux épinards et persil en grosses portions."],
      en: ["Keep green vegetable intake CONSISTENT day to day — don't skip, don't binge.", "Target: ~90–120 mcg/day. Above 250 mcg/day → INR instability risk.", "Prefer zucchini, eggplant, carrot over spinach and parsley in large portions."],
      ar: ["حافظ على كمية الخضار الخضراء ثابتة من يوم لآخر.", "الهدف: 90–120 ميكروغرام يومياً. أكثر من 250 → خطر عدم استقرار INR.", "فضّل الكوسة والباذنجان والجزر على السبانخ والبقدونس."],
    },
  },
  {
    id: "levothyrox_calcium", severity: "MEDIUM",
    drug_match: /levothyrox|levotiron|berlthyrox|euthyrox/i,
    lab_signals: [/.*/i],
    title: { fr: "Lévothyroxine + calcium/fer", en: "Levothyroxine + calcium / iron", ar: "ليفوثيروكسين + كالسيوم/حديد" },
    advice: {
      fr: ["Prendre à jeun, 30–60 min avant tout produit laitier ou fer.", "Séparer le café d'au moins 1 h (absorption -30 %)."],
      en: ["Take on empty stomach, 30–60 min before any dairy or calcium/iron supplement.", "Separate coffee by at least 1 hour (absorption reduced up to 30%)."],
      ar: ["تناول الدواء على معدة فارغة، قبل 30–60 دقيقة من أي ألبان أو مكمّل.", "افصل القهوة بساعة على الأقل (الامتصاص ينخفض حتى 30%)."],
    },
  },
  {
    id: "statin_grapefruit", severity: "HIGH",
    drug_match: /atorvastat|simvastat|lovastat|tahor|crestor|rosuvastat/i,
    lab_signals: [/.*/i],
    title: { fr: "Statine + pamplemousse (inhibition CYP3A4)", en: "Statin + grapefruit (CYP3A4 inhibition)", ar: "ستاتين + ليمون هندي (تثبيط CYP3A4)" },
    advice: {
      fr: ["Éviter le pamplemousse et son jus.", "Préférer orange et citron — sécuritaires avec les statines."],
      en: ["Avoid grapefruit and grapefruit juice entirely.", "Prefer orange and lemon — safe with statins."],
      ar: ["تجنّب الجريب فروت وعصيره.", "فضّل البرتقال والليمون — آمنان مع الستاتين."],
    },
  },
  {
    id: "metformin_b12", severity: "MEDIUM",
    drug_match: /metform|glucophage|diaguanid/i,
    lab_signals: [/.*/i],
    title: { fr: "Metformine + risque de carence en B12", en: "Metformin + B12 depletion risk", ar: "ميتفورمين + خطر نقص B12" },
    advice: {
      fr: ["Intégrer chaque semaine : foie, sardine, thon, œuf, laitages.", "Demander un dosage de B12 tous les 12 mois."],
      en: ["Include weekly: liver, sardine, tuna, egg, dairy.", "Request B12 lab test every 12 months on long-term metformin."],
      ar: ["أدرج أسبوعياً: كبدة، سردين، تونة، بيض، ألبان.", "اطلب فحص B12 كل 12 شهراً."],
    },
  },
];

// ── Deterministic "fast path" drug×food tiers ──────────────────────────────
export type FastTier = { drug: RegExp; food: RegExp; tier: Tier; en: string; fr: string; ar: string };

export const FAST_TIERS: FastTier[] = [
  { drug: /warfarin|acenocoum|sintrom|coumadin/i, food: /broccoli|cabbage|lettuce|arugula|soybean|olive_oil/i, tier: "MEDIUM",
    en: "Moderate vitamin K content — significant only at large portions or sudden changes.",
    fr: "Teneur modérée en vitamine K — significatif uniquement en grosses portions ou changement brusque.",
    ar: "محتوى متوسط من فيتامين K — مؤثر فقط في الكميات الكبيرة." },
  { drug: /atorvastat|simvastat|tahor|lovastat|rosuvastat|crestor/i, food: /grapefruit/i, tier: "HIGH",
    en: "CYP3A4 inhibition by grapefruit furanocoumarins — raises statin levels and myopathy risk.",
    fr: "Inhibition CYP3A4 par les furanocoumarines du pamplemousse — augmente le risque de myopathie.",
    ar: "تثبيط CYP3A4 بواسطة الجريب فروت — يرفع مستويات الستاتين ويزيد خطر اعتلال العضلات." },
  { drug: /levothyrox|levotiron|berlthyrox|euthyrox/i, food: /milk_cow|yogurt|lben|raib|cheese_white|sesame/i, tier: "MEDIUM",
    en: "Calcium binds levothyroxine — separate by 4 hours.",
    fr: "Le calcium se lie à la lévothyroxine — séparer de 4 heures.",
    ar: "الكالسيوم يرتبط بالليفوثيروكسين — افصلهما بـ 4 ساعات." },
  { drug: /levothyrox|levotiron|berlthyrox|euthyrox/i, food: /coffee/i, tier: "MEDIUM",
    en: "Coffee reduces levothyroxine absorption up to 30%. Wait 60 minutes after dose.",
    fr: "Le café réduit l'absorption de la lévothyroxine jusqu'à 30%. Attendre 60 min.",
    ar: "القهوة تقلل امتصاص الليفوثيروكسين حتى 30%. انتظر 60 دقيقة." },
  { drug: /omepraz|esomepraz|pantopraz|lansopraz|rabepraz|inipomp|mopral/i, food: /spinach|liver_beef|lentil|chickpea|sesame|fava|white_bean/i, tier: "MEDIUM",
    en: "PPIs reduce non-heme iron absorption. Add vitamin C and separate from PPI by 3+ hours.",
    fr: "Les IPP réduisent l'absorption du fer non-héminique. Ajouter vitamine C et espacer de 3 h.",
    ar: "مثبطات مضخة البروتون تقلل امتصاص الحديد غير الهيمي. أضف فيتامين C." },
  { drug: /ciprofloxac|levofloxac|moxifloxac|ofloxac/i, food: /milk_cow|yogurt|lben|raib|cheese_white/i, tier: "HIGH",
    en: "Fluoroquinolone chelates calcium — separate dairy by 2+ hours.",
    fr: "Les fluoroquinolones chélatent le calcium — espacer les laitages de 2 h.",
    ar: "الفلوروكينولونات تتحد مع الكالسيوم — افصل الألبان بساعتين." },
  { drug: /tetracyc|doxycyc|minocyc/i, food: /milk_cow|yogurt|lben|raib|cheese_white|sesame/i, tier: "HIGH",
    en: "Tetracyclines bind calcium — separate dairy by 2+ hours.",
    fr: "Les tétracyclines se lient au calcium — espacer les laitages de 2 h.",
    ar: "التتراسيكلين يرتبط بالكالسيوم — افصل الألبان بساعتين." },
];
