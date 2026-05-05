import { configureStore } from '@reduxjs/toolkit'
import counterReducer from '../features/counter/counterSlice'
import crmReducer from '../features/crm/crmSlice'

export const store = configureStore({
  reducer: {
    counter: counterReducer,
    crm: crmReducer,
  },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
