//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_PID_H
#define BALANCECAR_PID_H

typedef struct
{
    float target_;
    float actual_;
    float actual_pre_;
    float pid_output_;

    float kp_;
    float ki_;
    float kd_;

    float error_;
    float error_pre_;

    float p_output_;
    float i_output_;
    float d_output_;

    float output_max_;
    float output_min_;

    float out_offset_;
}PID_t;

void PID_init(PID_t * pid);

void PID_Update(PID_t * pid);

#endif //BALANCECAR_PID_H
