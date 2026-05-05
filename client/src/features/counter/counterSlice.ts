import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '../../store/store'

type CounterState = {
  value: number
}

const initialState: CounterState = {
  value: 0,
}

export const counterSlice = createSlice({
  name: 'counter',
  initialState,
  reducers: {
    increment: (state) => {
      state.value += 1
    },
    decrement: (state) => {
      state.value -= 1
    },
    incrementByAmount: (state, action: PayloadAction<number>) => {
      state.value += action.payload
    },
    resetCounter: (state) => {
      state.value = 0
    },
  },
})

export const { increment, decrement, incrementByAmount, resetCounter } =
  counterSlice.actions

export const selectCounterValue = (state: RootState) => state.counter.value

export default counterSlice.reducer
