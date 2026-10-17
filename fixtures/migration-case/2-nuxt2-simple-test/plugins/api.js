const items = [
  { id: '1', name: 'Keyboard', price: 12800, description: 'Mechanical keyboard' },
  { id: '2', name: 'Mouse', price: 6800, description: 'Wireless mouse' }
]

export default (_context, inject) => {
  inject('api', {
    async listItems() {
      return items
    },
    async getItem(id) {
      return items.find(item => item.id === id)
    }
  })
}
