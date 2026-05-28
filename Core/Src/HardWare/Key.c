//
// Created by ATINOMI on 2026/5/28.
//

#include "main.h"

uint8_t key_num;

uint8_t key_get_num(void)
{
    uint8_t temp;
    if (key_num)
    {
        temp = key_num;
        key_num = 0;
        return temp;
    }
    return 0;
}

uint8_t key_get_state(void)
{
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_1) == 0) return 1;

    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0) == 0) return 2;

    if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_5) == 0) return 3;

    if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_4) == 0) return 4;

    return 0;
}

void key_tick(void)
{
    static uint8_t count;
    static uint8_t current_state;
    static uint8_t previous_state;

    count++;
    if (count >= 20)
    {
        count = 0;

        previous_state = current_state;
        current_state = key_get_state();

        if (current_state == 0 && previous_state != 0)
        {
            key_num = previous_state;
        }
    }
}