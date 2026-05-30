//
// Created by ATINOMI on 2026/5/29.
//
#include "main.h"
#include "Algorithm/PID.h"

void PID_init(PID_t * pid)
{
    pid->target_    = 0;
    pid->actual_     = 0;
    pid->actual_pre_ = 0;
    pid->pid_output_       = 0;
    pid->error_            = 0;
    pid->error_pre_        = 0;
    pid->p_output_         = 0;
    pid->i_output_         = 0;
    pid->d_output_         = 0;
}

void PID_Update(PID_t * pid)
{
    /*误差传递*/
    pid->error_pre_ = pid->error_;
    pid->error_ = pid->target_ - pid->actual_;

    /*P项*/
    pid->p_output_ = pid->kp_ * pid->error_;

    /*I项*/
    if (pid->ki_ != 0)
    {
        pid->i_output_ += pid->ki_ * pid->error_;
    }
    else
    {
        pid->i_output_ = 0;
    }
    /*积分限幅*/
    if (pid->i_output_ > pid->output_max_) pid->i_output_ = pid->output_max_;
    if (pid->i_output_ < pid->output_min_) pid->i_output_ = pid->output_min_;

    /*D项 + 微分先行*/
    pid->d_output_ = -pid->kd_ * (pid->actual_- pid->actual_pre_);

    /*输出值*/
    pid->pid_output_ = pid->p_output_ + pid->i_output_ + pid->d_output_;

    /*输出偏移*/
    if (pid->pid_output_ > 0) pid->pid_output_ += pid->out_offset_;
    if (pid->pid_output_ < 0) pid->pid_output_ -= pid->out_offset_;

    /*输出限幅*/
    if (pid->pid_output_ > pid->output_max_) pid->pid_output_ = pid->output_max_;
    if (pid->pid_output_ < pid->output_min_) pid->pid_output_ = pid->output_min_;

    /*实际值传递*/
    pid->actual_pre_ = pid->actual_;
}