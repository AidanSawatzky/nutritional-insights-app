//had to npm install mongodb
//had to npm install csv-parse

const { MongoClient } = require("mongodb");
const client = new MongoClient("mongodb+srv://louisbella_db_user:ASIr488YpCiiFFaa@cluster0.qyvxujx.mongodb.net/?appName=Cluster0");



const fs = require("fs");
const { parse } = require("csv-parse/sync");
const store = fs.readFileSync("/Users/origamix/Desktop/DashboardUI/cleaned_with_ratios copy.csv", "utf-8");
const rows = parse(store, { columns: true });



const recipes = [];

//Diet_type,Recipe_name,Cuisine_type,Protein(g),Carbs(g),Fat(g),Extraction_day,Extraction_time,Protein_to_Carbs_ratio,Carbs_to_Fat_ratio
for (const row of rows) {
  recipes.push({
    Diet_Type: row["Diet_type"],
    Recipe_Name: row["Recipe_name"],
    Cuisine_Type: row["Cuisine_type"],
    Protein: parseFloat(row["Protein(g)"]),
    Carbs: parseFloat(row["Carbs(g)"]),
    Fat: parseFloat(row["Fat(g)"])

  });
}



async function main() {
  await client.connect();
  const db = client.db("Store");
  //don't allow doubles of data
  await db.collection("recipes").deleteMany({});
  await db.collection("recipes").insertMany(recipes);
  await client.close();

}

main();
