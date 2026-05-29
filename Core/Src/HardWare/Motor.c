//
// Created by ATINOMI on 2026/5/29.
//

#include "main.h"

extern TIM_HandleTypeDef htim2;

void motor_set_pwm(uint8_t n, int8_t pwm)
{
    if (n == 1)
    {
        if (pwm >=0 )
        {
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pwm);
        }
        else
        {
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, -pwm);  // 要加负号喵
        }
    }
    else if (n == 2)
    {
        if (pwm >=0 )
        {
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, GPIO_PIN_SET);
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, pwm);
        }
        else
        {
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, GPIO_PIN_RESET);
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, -pwm);
        }
    }

}