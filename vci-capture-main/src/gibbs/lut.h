#ifndef lut_h
#define lut_h

/* 12-bit to 10-bit LUT for low-relative-error transmission of image data */
/* (C) 2023, Matthias Hullin <hullin@cs.uni-bonn.de>, University of Bonn  */

#include <iostream>
#include <cmath>

#define LUT_SIZE 65536
#define min_error 0.1
namespace lut
{


/* lut_general: general linear-polynomial LUT and inverse LUT for bitrate reduction in imaging. Default parameters chosen for best performance in 12bit sensor data to 10bit stream reduction */

  template <typename T = unsigned short, int num_values_in = 4096, int num_values_out = 1024, int exponent = 4>
  class lut_general
  {

    T lut[LUT_SIZE];
    T ilut[LUT_SIZE];
  
  public:
    float f_1(float y) const // *inverse* LUT defined using polynomial function such that it is linear for small values
    {
      y /= num_values_out;
      float factor = (float(num_values_in)/num_values_out);
      return num_values_in * (y+(factor-1)*powf(y,exponent))/factor;
    }

    float f(const float x) const // so the *forward* mapping has to be done numerically (here, simple nested interval scheme)
    {
      float l = 0; float r = num_values_out;
      while(fabs(f_1(l)-x)>min_error)
      {
        float f_1_middle = f_1((l+r)/2.f);
        if (f_1_middle > x)
          r = (l+r)/2.f;
        else
          l = (l+r)/2.f;
      }
      return l;
    }

    lut_general() // fill lut and ilut with values
    {

      for (int i = 0; i < num_values_in; ++i)
        lut[i] = round(f(i));
      for (int i = num_values_in; i < LUT_SIZE; ++i)
        lut[i] = num_values_out-1;

      for (int i = 0; i < num_values_out; ++i)
        ilut[i] = round(f_1(i));
      for (int i = num_values_out; i < LUT_SIZE; ++i)
        ilut[i] = num_values_in-1;
    }

    T compress(const T in) const // forward lookup
    {
      return lut[in];
    }

    T uncompress(const T in) const // inverse lookup
    {
      return ilut[in];
    }

    const T *lut_data() // pointer to lut
    {
      return (const T *)&lut;
    }
    const T *ilut_data() // pointer to ilut
    {
      return (const T *)&ilut;
    }
  };



#if 0


  template <typename T = unsigned short>
  class lut12_10
  {

    T lut[LUT_SIZE];
    T ilut[LUT_SIZE];

  public:
    lut12_10()
    {
      for (int i = 0; i < 1024; ++i)
      {
        float f = (i / 1024.f);
        ilut[i] = T(round(1024 * (f + 3.f * f * f)));
        if (ilut[i] > 4095)
        {
          ilut[i] = 4095;
        }
      }
      for (int i = 1024; i < LUT_SIZE; ++i)
      {
        ilut[i] = 4095;
      }

      for (int i = 0; i < 4096; ++i)
      {
        float f = (i / 1024.f);
        lut[i] = T(round(1024 * (1.f / 6.f * (sqrtf(12 * f + 1.f) - 1.f))));
        if (lut[i] > 1023)
        {
          lut[i] = 1023;
        }
      }
      for (int i = 4096; i < LUT_SIZE; ++i)
      {
        lut[i] = 1023;
      }
    }

    T compress(const T in) const
    {
      return lut[in];
    }

    T uncompress(const T in) const
    {
      return ilut[in];
    }

    const T *lut_data()
    {
      return (const T *)&lut;
    }
    const T *ilut_data()
    {
      return (const T *)&ilut;
    }
  };

  template <typename T = unsigned short>
  class lut12_8
  {

    T lut[LUT_SIZE];
    T ilut[LUT_SIZE];

  public:
    lut12_8()
    {
      for (int i = 0; i < 256; ++i)
      {
        float f = (i / 256.f);
        ilut[i] = T(round(256 * (f + 15.f * f * f)));
        if (ilut[i] > 4095)
        {
          ilut[i] = 4095;
        }
      }
      for (int i = 256; i < LUT_SIZE; ++i)
      {
        ilut[i] = 4095;
      }

      for (int i = 0; i < 4096; ++i)
      {
        float f = (i / 256.f);
        lut[i] = T(round(256 * (1.f / 30.f * (sqrtf(60 * f + 1.f) - 1.f))));
        if (lut[i] > 255)
        {
          lut[i] = 255;
        }
      }
      for (int i = 4096; i < LUT_SIZE; ++i)
      {
        lut[i] = 255;
      }
    }

    T compress(const T in) const
    {
      return lut[in];
    }

    T uncompress(const T in) const
    {
      return ilut[in];
    }

    const T *lut_data()
    {
      return (const T *)&lut;
    }
    const T *ilut_data()
    {
      return (const T *)&ilut;
    }
  };

  bool unit_test()
  {
    std::cout << "lut::unit_test():";
    lut12_10 lut;
    unsigned short out[4096];
    for (int i = 0; i < 4096; ++i)
    {
      int temp = lut.compress(i);
      out[i] = lut.uncompress(temp);

      float rel_error = abs(int(out[i]) - i) / float(i);
      //if (rel_error > 0.01)
      //  std::cerr << i << " -> " << temp << " -> " << out[i] << " (rel. error: " << rel_error * 100 << "%)" << std::endl;
      if (rel_error > 0.1)
      {
        std::cout << "Error > 10% - unit test failed" << std::endl;
        return false;
      }
    }
    std::cout << " passed." << std::endl;

    return true;
  }

#endif
}


#endif // def lut.h
