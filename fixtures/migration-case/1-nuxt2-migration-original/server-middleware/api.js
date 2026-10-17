const express = require('express')
const app = express()

const products = [
  { id: 1, name: 'legacy keyboard', description: 'A Vue2-era keyboard', price: 49.99 },
  { id: 2, name: 'migration mouse', description: 'Useful during framework upgrades', price: 29.99 }
]

app.get('/products', (req, res) => {
  res.json(products)
})

app.get('/products/:id', (req, res) => {
  const product = products.find(item => String(item.id) === req.params.id)
  if (!product) return res.status(404).json({ message: 'not found' })
  res.json(product)
})

app.get('/profile', (req, res) => {
  res.json({ name: 'Demo User', email: 'demo@example.com' })
})

module.exports = app
